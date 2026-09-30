#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Robou
"""Register in a Wine prefix a "Brother PT-P700" printer that P-touch Editor 6 recognises.

P-touch Editor identifies its printers by the Windows *driver name*. Wine cannot load Brother's
driver, so we register a printer carrying that name, backed by Wine's generic PostScript driver
(wineps) and a PPD that imitates Brother's driver (180 dpi, tape IDs). The PostScript it produces
is handed to a Linux command (redirected port) that sends it to the label printer.

usage: install.py [--tape ID] [--spool COMMAND] [--uninstall]
"""
import argparse, os, shutil, struct, subprocess, sys, tempfile

import make_ppd

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'Brother PT-P700'
PORT = 'PTP700:'
PRINT = r'System\CurrentControlSet\Control\Print'
WININI = r'Software\Microsoft\Windows NT\CurrentVersion'
ENVS = {'Windows NT x86': 'w32x86', 'Windows x64': 'x64'}


def devmode(tape_id):
    """Public DEVMODEA only (dmDriverExtra = 0): wineps fills in its private part from the PPD.
    Every field of its default DEVMODE must be flagged as present, otherwise it ignores ours."""
    name, width, length = make_ppd.tape(tape_id)
    fields = 0x1ff1f  # orientation, paper, length, width, scale, copies, source, quality,
                      # colour, duplex, Y resolution, TrueType, collate, form name
    b = struct.pack('<32sHHHHI', NAME.encode('ascii'), 0x30a, 1, 156, 0, fields)
    b += struct.pack('<13h',
                     2,              # dmOrientation: landscape, like Brother's driver
                     tape_id,        # dmPaperSize: Brother tape ID
                     length, width,  # 1/10 mm
                     100, 1,         # scale, copies
                     7,              # dmDefaultSource: automatic
                     make_ppd.DPI,   # dmPrintQuality
                     1,              # dmColor: monochrome
                     1,              # dmDuplex: simplex
                     make_ppd.DPI,   # dmYResolution
                     3,              # dmTTOption
                     0)              # dmCollate
    b += struct.pack('<32s', name.encode('ascii'))
    return b.ljust(156, b'\0')


def reg_install(tape_id, spool):
    o = ['Windows Registry Editor Version 5.00', '']
    for env in ENVS:
        o += ['[HKEY_LOCAL_MACHINE\\%s\\Environments\\%s\\Drivers\\Version-3\\%s]' % (PRINT, env, NAME),
              '"Configuration File"="wineps.drv"',
              '"Data File"="%s.ppd"' % NAME,
              '"Datatype"="RAW"',
              '"Dependent Files"=hex(7):00,00',
              '"Driver"="wineps.drv"',
              '"Help File"=""',
              '"Monitor"=""',
              '"Previous Names"=hex(7):00,00',
              '"Print Processor"="winprint"',
              '"Version"=dword:00000003', '']
    o += ['[HKEY_LOCAL_MACHINE\\%s\\Printers\\%s]' % (PRINT, NAME),
          '"Attributes"=dword:00000000',
          '"Datatype"="RAW"',
          '"Default DevMode"=hex:' + ','.join('%02x' % x for x in devmode(tape_id)),
          '"Default Priority"=dword:00000000',
          '"Description"="%s"' % NAME,
          '"dnsTimeout"=dword:00000000',
          '"Location"=""',
          '"Name"="%s"' % NAME,
          '"Parameters"=""',
          '"Port"="%s"' % PORT,   # neither "CUPS:" nor "LPR:": Wine does not delete it at startup
          '"Print Processor"="wineps"',
          '"Printer Driver"="%s"' % NAME,
          '"Priority"=dword:00000000',
          '"Separator File"=""',
          '"Share Name"=""',
          '"StartTime"=dword:00000000',
          '"Status"=dword:00000000',
          '"txTimeout"=dword:00000000',
          '"UntilTime"=dword:00000000', '',
          r'[HKEY_CURRENT_USER\Software\Wine\Printing\Spooler]',
          '"%s"="|%s"' % (PORT, spool.replace('\\', '\\\\').replace('"', '\\"')), '',
          # "win.ini" tables: this is where CreateDC looks up a printer's GDI driver
          '[HKEY_CURRENT_USER\\%s\\Devices]' % WININI,
          '"%s"="wineps.drv,%s"' % (NAME, PORT), '',
          '[HKEY_CURRENT_USER\\%s\\PrinterPorts]' % WININI,
          '"%s"="wineps.drv,%s,15,45"' % (NAME, PORT), '']
    return o


def reg_uninstall():
    o = ['Windows Registry Editor Version 5.00', '']
    for env in ENVS:
        o += ['[-HKEY_LOCAL_MACHINE\\%s\\Environments\\%s\\Drivers\\Version-3\\%s]' % (PRINT, env, NAME), '']
    o += ['[-HKEY_LOCAL_MACHINE\\%s\\Printers\\%s]' % (PRINT, NAME), '',
          r'[HKEY_CURRENT_USER\Software\Wine\Printing\Spooler]', '"%s"=-' % PORT, '',
          '[HKEY_CURRENT_USER\\%s\\Devices]' % WININI, '"%s"=-' % NAME, '',
          '[HKEY_CURRENT_USER\\%s\\PrinterPorts]' % WININI, '"%s"=-' % NAME, '']
    return o


def regedit(lines):
    with tempfile.NamedTemporaryFile('w', suffix='.reg', encoding='utf-16', delete=False) as f:
        f.write('\r\n'.join(lines))
    try:
        return subprocess.call(['wine', 'regedit', '/S', f.name], env=dict(os.environ, WINEDEBUG='-all'))
    finally:
        os.unlink(f.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--tape', type=int, default=258,
                    help='default tape ID (257=6 mm, 258=9 mm, 259=12 mm, 260=18 mm, 261=24 mm)')
    ap.add_argument('--spool', default=os.path.join(HERE, 'ptp700-print'),
                    help='Linux command that receives the PostScript on its standard input')
    ap.add_argument('--uninstall', action='store_true', help='remove the printer from the Wine prefix')
    a = ap.parse_args()

    prefix = os.environ.get('WINEPREFIX', os.path.expanduser('~/.wine'))
    drivers = os.path.join(prefix, 'drive_c/windows/system32/spool/drivers')

    if a.uninstall:
        rc = regedit(reg_uninstall())
        for d in ENVS.values():
            p = os.path.join(drivers, d, '3', NAME + '.ppd')
            if os.path.exists(p):
                os.unlink(p)
        print('printer "%s" removed from %s (rc=%d)' % (NAME, prefix, rc))
        return rc

    ppd = os.path.join(HERE, NAME + '.ppd')
    make_ppd.main(ppd, a.tape)
    for d in ENVS.values():
        os.makedirs(os.path.join(drivers, d, '3'), exist_ok=True)
        shutil.copy(ppd, os.path.join(drivers, d, '3'))
    rc = regedit(reg_install(a.tape, a.spool))
    print('printer "%s" installed in %s (default tape: %s, rc=%d)'
          % (NAME, prefix, make_ppd.tape(a.tape)[0], rc))
    return rc


if __name__ == '__main__':
    sys.exit(main())

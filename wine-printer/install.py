#!/usr/bin/env python3
"""Déclare dans un préfixe Wine une imprimante « Brother PT-P700 » que P-touch Editor 6 reconnaît.

P-touch Editor identifie ses imprimantes par le *nom du pilote* Windows. Wine ne sait pas charger
le pilote Brother ; on enregistre donc une imprimante portant ce nom, adossée au pilote PostScript
générique de Wine (wineps) et à un PPD qui imite le pilote Brother (180 dpi, identifiants de ruban).
Le flux PostScript produit est remis à une commande Linux (port redirigé) qui se charge de
l'envoyer à l'étiqueteuse.

usage : install.py [--tape ID] [--spool COMMANDE] [--uninstall]
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
    """DEVMODEA public seul (dmDriverExtra = 0) : wineps complète sa partie privée depuis le PPD.
    Tous les champs de son DEVMODE par défaut doivent être marqués présents, sinon il l'ignore."""
    name, width, length = make_ppd.tape(tape_id)
    fields = 0x1ff1f  # orientation, papier, longueur, largeur, échelle, copies, bac, qualité,
                      # couleur, recto-verso, résolution Y, TrueType, assemblage, nom du format
    b = struct.pack('<32sHHHHI', NAME.encode('ascii'), 0x30a, 1, 156, 0, fields)
    b += struct.pack('<13h',
                     2,              # dmOrientation : paysage, comme le pilote Brother
                     tape_id,        # dmPaperSize : identifiant Brother du ruban
                     length, width,  # 1/10 mm
                     100, 1,         # échelle, copies
                     7,              # dmDefaultSource : automatique
                     make_ppd.DPI,   # dmPrintQuality
                     1,              # dmColor : monochrome
                     1,              # dmDuplex : recto
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
          '"Port"="%s"' % PORT,   # ni « CUPS: » ni « LPR: » : Wine ne la supprime pas au démarrage
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
          # tables « win.ini » : c'est là que CreateDC trouve le pilote GDI d'une imprimante
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
                    help='identifiant du ruban par défaut (257=6 mm, 258=9 mm, 259=12 mm, 260=18 mm, 261=24 mm)')
    ap.add_argument('--spool', default=os.path.join(HERE, 'ptp700-print'),
                    help='commande Linux qui reçoit le PostScript sur son entrée standard')
    ap.add_argument('--uninstall', action='store_true')
    a = ap.parse_args()

    prefix = os.environ.get('WINEPREFIX', os.path.expanduser('~/.wine'))
    drivers = os.path.join(prefix, 'drive_c/windows/system32/spool/drivers')

    if a.uninstall:
        rc = regedit(reg_uninstall())
        for d in ENVS.values():
            p = os.path.join(drivers, d, '3', NAME + '.ppd')
            if os.path.exists(p):
                os.unlink(p)
        print('imprimante « %s » retirée de %s (rc=%d)' % (NAME, prefix, rc))
        return rc

    ppd = os.path.join(HERE, NAME + '.ppd')
    make_ppd.main(ppd, a.tape)
    for d in ENVS.values():
        os.makedirs(os.path.join(drivers, d, '3'), exist_ok=True)
        shutil.copy(ppd, os.path.join(drivers, d, '3'))
    rc = regedit(reg_install(a.tape, a.spool))
    print('imprimante « %s » installée dans %s (ruban par défaut : %s, rc=%d)'
          % (NAME, prefix, make_ppd.tape(a.tape)[0], rc))
    return rc


if __name__ == '__main__':
    sys.exit(main())

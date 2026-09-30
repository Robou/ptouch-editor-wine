#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Robou
"""Generate the PostScript PPD that Wine (wineps) uses for the "Brother PT-P700" printer.

Goal: make Wine present P-touch Editor with the same characteristics as Brother's Windows driver:
180 dpi, and the same paper IDs (dmPaperSize). Wine numbers unknown page sizes from 256
(DMPAPER_USER) in PPD order, so "reserved" sizes are inserted until each tape lands on its
Brother ID.
"""
import sys

DPI = 180
FEED_DOTS = 14          # minimum margin at each end of a label (2 mm)
DEFAULT_LEN_DOTS = 709  # 100 mm

# Brother ID (dmPaperSize), name, tape width (dots), printable width (dots)
TAPES = [
    (263, '3.5 mm', 24, 24), (257, '6 mm', 42, 32), (258, '9 mm', 64, 50),
    (259, '12 mm', 84, 70), (260, '18 mm', 128, 112), (261, '24 mm', 170, 128),
    (279, '12 mm x 2', 154, 140), (280, '18 mm x 2', 240, 224), (281, '24 mm x 2', 298, 256),
    (285, '12 mm x 3', 224, 210), (286, '18 mm x 3', 352, 336), (287, '24 mm x 3', 426, 384),
    (291, '12 mm x 4', 294, 280), (292, '18 mm x 4', 464, 448), (293, '24 mm x 4', 554, 512),
    (420, 'HS 5.2 mm', 36, 20), (415, 'HS 5.8 mm', 40, 28), (416, 'HS 8.8 mm', 62, 48),
    (421, 'HS 9.0 mm', 64, 44), (422, 'HS 11.2 mm', 80, 50), (417, 'HS 11.7 mm', 82, 66),
    (418, 'HS 17.7 mm', 126, 106), (423, 'HS 21.0 mm', 148, 120), (419, 'HS 23.6 mm', 168, 128),
]
DEFAULT_ID = 261
EPS = 0.01          # in dots


def tape(pid):
    """(name, width in 1/10 mm, default length in 1/10 mm) of a tape."""
    for t in TAPES:
        if t[0] == pid:
            return t[1], round(t[2] * 254.0 / DPI), round(DEFAULT_LEN_DOTS * 254.0 / DPI)
    raise KeyError(pid)


def pt(dots):
    return ('%.3f' % (dots * 72.0 / DPI)).rstrip('0').rstrip('.')


def main(out, default_id=DEFAULT_ID):
    by_id = {t[0]: t for t in TAPES}
    pages = []  # (key, label, width, printable width)
    for pid in range(256, max(by_id) + 1):
        if pid in by_id:
            _, name, w, area = by_id[pid]
            pages.append(('p%d' % pid, name, w, area))
        else:
            pages.append(('r%d' % pid, 'reserved %d' % pid, 170, 128))
    default = 'p%d' % default_id

    L = DEFAULT_LEN_DOTS
    o = []
    o.append('*PPD-Adobe: "4.3"')
    o.append('*%% PPD for Wine (wineps): imitates the Brother PT-P700 Windows driver.')
    o.append('*FormatVersion: "4.3"')
    o.append('*FileVersion: "1.0"')
    o.append('*LanguageVersion: English')
    o.append('*LanguageEncoding: ISOLatin1')
    o.append('*PCFileName: "BRPTP700.PPD"')
    o.append('*Manufacturer: "Brother"')
    o.append('*Product: "(PT-P700)"')
    o.append('*ModelName: "Brother PT-P700"')
    o.append('*ShortNickName: "Brother PT-P700"')
    o.append('*NickName: "Brother PT-P700"')
    o.append('*PSVersion: "(3010.000) 0"')
    o.append('*LanguageLevel: "3"')
    o.append('*ColorDevice: False')
    o.append('*DefaultColorSpace: Gray')
    o.append('*FileSystem: False')
    o.append('*Throughput: "1"')
    o.append('*LandscapeOrientation: Plus90')
    o.append('*TTRasterizer: Type42')
    o.append('')
    o.append('*OpenUI *Resolution/Resolution: PickOne')
    o.append('*DefaultResolution: %ddpi' % DPI)
    o.append('*Resolution %ddpi/%d dpi: "<</HWResolution[%d %d]>>setpagedevice"' % (DPI, DPI, DPI, DPI))
    o.append('*CloseUI: *Resolution')
    o.append('')
    # Without a Duplex option, wineps clears DM_DUPLEX in the DEVMODE it stores, then rejects that
    # DEVMODE at the next start and falls back on its built-in defaults (300 dpi).
    o.append('*OpenUI *Duplex/Duplex: PickOne')
    o.append('*DefaultDuplex: None')
    o.append('*Duplex None/Off: ""')
    o.append('*CloseUI: *Duplex')
    o.append('')
    o.append('*OpenUI *PageSize/Page Size: PickOne')
    o.append('*OrderDependency: 100 AnySetup *PageSize')
    o.append('*DefaultPageSize: ' + default)
    for key, name, w, _ in pages:
        o.append('*PageSize %s/%s: "<</PageSize[%s %s]/ImagingBBox null>>setpagedevice"' % (key, name, pt(w), pt(L)))
    o.append('*CloseUI: *PageSize')
    o.append('')
    o.append('*OpenUI *PageRegion: PickOne')
    o.append('*OrderDependency: 100 AnySetup *PageRegion')
    o.append('*DefaultPageRegion: ' + default)
    for key, name, w, _ in pages:
        o.append('*PageRegion %s/%s: "<</PageSize[%s %s]/ImagingBBox null>>setpagedevice"' % (key, name, pt(w), pt(L)))
    o.append('*CloseUI: *PageRegion')
    o.append('')
    o.append('*DefaultImageableArea: ' + default)
    for key, name, w, area in pages:
        m = (w - area) / 2.0
        # + EPS: wineps truncates when converting points to pixels; without it 2.8 pt gives 6 px, not 7
        o.append('*ImageableArea %s/%s: "%s %s %s %s"' % (key, name, pt(m + EPS), pt(FEED_DOTS + EPS),
                                                       pt(m + area + EPS), pt(L - FEED_DOTS + EPS)))
    o.append('')
    o.append('*DefaultPaperDimension: ' + default)
    for key, name, w, _ in pages:
        o.append('*PaperDimension %s/%s: "%s %s"' % (key, name, pt(w), pt(L)))
    o.append('')
    open(out, 'w', encoding='latin-1').write('\n'.join(o) + '\n')
    print('wrote', out, '(%d page sizes)' % len(pages))


if __name__ == '__main__':
    main(sys.argv[1])

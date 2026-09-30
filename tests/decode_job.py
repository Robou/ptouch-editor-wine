#!/usr/bin/env python3
"""Décode un flux de commandes raster PT-P700 (tel que produit par ptp700-print) et le décrit.
Sert à vérifier un travail sans imprimante : decode_job.py travail.bin [aperçu.pbm]"""
import sys

def unpack(d):
    out, i = bytearray(), 0
    while i < len(d):
        n = d[i]
        if n < 128:
            out += d[i + 1:i + 2 + n]; i += 2 + n
        else:
            out += bytes([d[i + 1]]) * (257 - n); i += 2
    return bytes(out)

def decode(b):
    i = 0
    while i < len(b) and b[i] == 0:
        i += 1
    print('invalidation : %d octets nuls' % i)
    pages, lines = [], []
    while i < len(b):
        c = b[i]
        if b[i:i + 2] == b'\x1b@': print('initialisation'); i += 2
        elif b[i:i + 3] == b'\x1bia': print('mode raster', b[i + 3]); i += 4
        elif b[i:i + 3] == b'\x1biz':
            n = b[i + 3:i + 13]
            print('infos : drapeaux=%#x type=%#x largeur=%d mm longueur=%d lignes=%d page=%d'
                  % (n[0], n[1], n[2], n[3], int.from_bytes(n[4:8], 'little'), n[8])); i += 13
        elif b[i:i + 3] == b'\x1biM': print('modes : coupe auto=%d miroir=%d' % (b[i + 3] >> 6 & 1, b[i + 3] >> 7)); i += 4
        elif b[i:i + 3] == b'\x1biK': print('avancé : sans chaînage=%d' % (b[i + 3] >> 3 & 1)); i += 4
        elif b[i:i + 3] == b'\x1bid': print('marge : %d points' % int.from_bytes(b[i + 3:i + 5], 'little')); i += 5
        elif c == 0x4d: print('compression', b[i + 1]); i += 2
        elif c == 0x5a: lines.append(bytes(16)); i += 1
        elif c == 0x47:
            n = int.from_bytes(b[i + 1:i + 3], 'little'); d = unpack(b[i + 3:i + 3 + n])
            assert len(d) == 16, 'ligne de %d octets' % len(d)
            lines.append(d); i += 3 + n
        elif c in (0x0c, 0x1a):
            print('%s : %d lignes raster' % ('impression' if c == 0x0c else 'impression + avance', len(lines)))
            pages.append(lines); lines = []; i += 1
        else:
            raise SystemExit('octet inattendu %#x à la position %d' % (c, i))
    return pages

pages = decode(open(sys.argv[1], 'rb').read())
if len(sys.argv) > 2:
    lines = [l for p in pages for l in p]
    w, stride = len(lines), (len(lines) + 7) // 8
    img = bytearray(stride * 128)
    for x, l in enumerate(lines):
        for y in range(128):
            if l[y >> 3] & (0x80 >> (y & 7)):
                img[y * stride + (x >> 3)] |= 0x80 >> (x & 7)
    open(sys.argv[2], 'wb').write(b'P4\n%d %d\n' % (w, 128) + bytes(img))
    rows = [y for y in range(128) if any(l[y >> 3] & (0x80 >> (y & 7)) for l in lines)]
    print('points de tête utilisés : %d à %d' % (rows[0], rows[-1]))

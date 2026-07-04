#!/usr/bin/env python3
"""
Convert Atari Falcon rev4 ("Sparrow") Seetrax RANGER RS-274-D photoplot
files (.SPL) to modern RS-274X.

Source format (from SPARROW.USR):
  - Gerber 6000/6200 photoplotter dialect, no G codes, no arcs
  - Absolute imperial coordinates, 5.3 format (units of 0.001")
  - Leading zeros omitted, D codes modal
  - Aperture wheel defined in SPARROW.USR symbol table (positions 10..80)

Output:
  - RS-274X, %FSLAX24Y24*% %MOIN*% (units of 0.0001")
  - Explicit D01/D02/D03 on every coordinate block (no modality)
  - Apertures from the USR table: shape 1 -> C (circle),
    shape 2 -> R (square), shape 3 (draw-only) -> C,
    moire targets (D19/D46) -> aperture macros
  - Coordinates translated by (-4849, -7746) mil so the image lands in
    the same frame as Drill_PTH.drl (rev2 KiCad coordinate frame)
"""

import re
import sys

# (shape, size_mil) from SPARROW.USR symbol table.
# shape: 1 = round, 2 = square, 3 = special (only ever used to draw), moire = target
APERTURES = {
    10: (1, 55), 11: (2, 55), 12: (1, 50), 13: (2, 95), 14: (1, 75),
    15: (2, 75), 16: (1, 95), 17: (1, 100), 18: (1, 150), 19: ('moire', 157),
    20: (1, 250), 21: (1, 315), 22: (1, 200), 23: (2, 70), 24: (1, 510),
    25: (2, 50), 26: (1, 80), 27: (1, 8), 28: (1, 120), 29: (2, 40),
    30: (1, 170), 31: (1, 12), 32: (2, 20), 33: (1, 70), 34: (1, 270),
    35: (1, 453), 36: (1, 60), 37: (1, 185), 38: (2, 35), 39: (1, 158),
    40: (2, 15), 41: (1, 530), 42: (1, 335), 43: (2, 80), 44: (1, 40),
    45: (1, 35), 46: ('moire', 177), 47: (1, 70), 48: (1, 315), 49: (2, 25),
    50: (1, 138), 51: (1, 170), 52: (1, 130), 53: (1, 130), 54: (3, 50),
    55: (1, 220), 56: (2, 60), 57: (1, 110), 58: (1, 190), 59: (1, 195),
    60: (3, 28), 61: (2, 110), 62: (1, 433), 63: (1, 125), 64: (1, 31),
    65: (1, 11), 66: (2, 11), 67: (3, 11), 68: (1, 190), 69: (1, 4),
    70: (1, 10), 71: (1, 12), 72: (1, 15), 73: (1, 20), 74: (1, 25),
    75: (1, 30), 76: (3, 8), 77: (2, 30), 78: (1, 165), 79: (2, 100),
    80: (1, 32),
}

# Translation (mil): SPL frame -> drill (rev2 KiCad) frame
OFF_X = -4849
OFF_Y = -7746

LINE_RE = re.compile(
    r'^(?:\*|M02\*|D(?P<sel>\d+)\*|'
    r'(?:X(?P<x>-?\d+))?(?:Y(?P<y>-?\d+))?(?:D(?P<op>0[123]))?\*)$')


def parse_spl(path):
    """Yield ('select', dcode) | ('op', x_mil, y_mil, 'D0n') in file order.

    Coordinates absolute mils, modal D codes resolved, modal X/Y resolved.
    """
    x = y = 0
    lastop = None
    cmds = []
    with open(path, 'r') as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line == '*':
                continue
            if line == 'M02*':
                break
            m = LINE_RE.match(line)
            if not m:
                raise ValueError(f'{path}:{lineno}: unparseable line {line!r}')
            if m.group('sel'):
                cmds.append(('select', int(m.group('sel'))))
                continue
            gx, gy, gop = m.group('x'), m.group('y'), m.group('op')
            if gx is None and gy is None:
                continue
            if gx is not None:
                x = int(gx)
            if gy is not None:
                y = int(gy)
            op = 'D' + gop if gop else lastop
            if op is None:
                # Coordinate before any operation code: treat as move
                op = 'D02'
            lastop = op
            cmds.append(('op', x, y, op))
    # Drop leading / trailing park moves to the plotter origin (0,0):
    # they draw nothing and only distort the image bounding box.
    while cmds and cmds[0][0] == 'op' and cmds[0][3] == 'D02' and \
            cmds[0][1] == 0 and cmds[0][2] == 0:
        cmds.pop(0)
    while cmds and cmds[-1][0] == 'op' and cmds[-1][3] == 'D02':
        # trailing moves (typically back to 0,0) plot nothing
        cmds.pop()
    return cmds


MACROS = {
    157: (
        '%AMTARGET157*\n'
        '0 Photoplotter registration target (moire with cross), 157 mil*\n'
        '1,1,0.157,0,0*\n'
        '1,0,0.133,0,0*\n'
        '1,1,0.090,0,0*\n'
        '1,0,0.066,0,0*\n'
        '21,1,0.157,0.010,0,0,0*\n'
        '21,1,0.010,0.157,0,0,0*%\n'
    ),
    177: (
        '%AMTARGET177*\n'
        '0 Photoplotter registration target (moire with cross), 177 mil*\n'
        '1,1,0.177,0,0*\n'
        '1,0,0.153,0,0*\n'
        '1,1,0.100,0,0*\n'
        '1,0,0.076,0,0*\n'
        '21,1,0.177,0.010,0,0,0*\n'
        '21,1,0.010,0.177,0,0,0*%\n'
    ),
}


def aperture_def(d):
    shape, size = APERTURES[d]
    inch = size / 1000.0
    if shape == 'moire':
        return f'%ADD{d}TARGET{size}*%\n'
    if shape == 2:
        return f'%ADD{d}R,{inch:.4f}X{inch:.4f}*%\n'
    # shape 1 and shape 3 (shape 3 only ever draws; stroke width is all
    # that matters, render as circle)
    return f'%ADD{d}C,{inch:.4f}*%\n'



FLOOD_RECT = (4950, 8150, 23050, 20150)  # D31 frame rect present in SPARL2/SPARL5


MOIRE_RINGS = {19: (91, 92, 785), 46: (93, 94, 885)}  # outer, inner, half-length (0.1mil)


def emit_body(out, cmds, srcname):
    cur = None
    pending = None  # moire dcode selected but not yet emitted
    for c in cmds:
        if c[0] == 'select':
            if APERTURES[c[1]][0] == 'moire':
                pending = c[1]
                cur = None
            else:
                pending = None
                if c[1] != cur:
                    out.append(f'D{c[1]}*\n')
                    cur = c[1]
        else:
            _, x, y, op = c
            xo = (x + OFF_X) * 10
            yo = (y + OFF_Y) * 10
            if pending is not None and op == 'D03':
                outer, inner, hl = MOIRE_RINGS[pending]
                out.append(f'D{outer}*\nX{xo}Y{yo}D03*\n')
                out.append(f'D{inner}*\nX{xo}Y{yo}D03*\n')
                out.append('D90*\n')
                out.append(f'X{xo - hl}Y{yo}D02*\nX{xo + hl}Y{yo}D01*\n')
                out.append(f'X{xo}Y{yo - hl}D02*\nX{xo}Y{yo + hl}D01*\n')
                cur = 90
            else:
                out.append(f'X{xo}Y{yo}{op}*\n')


def header(out, layer_name, src_desc, function, used, extra_comments=()):
    out.append(f'G04 {layer_name} - Atari Falcon rev4 (Sparrow, C303006-001)*\n')
    out.append(f'G04 Converted from Seetrax RANGER RS-274-D: {src_desc}*\n')
    out.append('G04 Apertures from SPARROW.USR symbol table*\n')
    out.append(f'G04 Translated by ({OFF_X},{OFF_Y}) mil into the '
               f'Drill_PTH.drl (rev2 KiCad) coordinate frame*\n')
    for c in extra_comments:
        out.append(f'G04 {c}*\n')
    if function:
        out.append(f'%TF.FileFunction,{function}*%\n')
    out.append('%FSLAX24Y24*%\n')
    out.append('%MOIN*%\n')
    out.append('%IPPOS*%\n')
    moire_used = any(APERTURES[d][0] == 'moire' for d in used)
    for d in used:
        if APERTURES[d][0] == 'moire':
            continue
        out.append(aperture_def(d))
    if moire_used:
        out.append('G04 Registration target (moire w/ cross) tools, decomposed*\n')
        out.append('G04 from the original photohead target apertures D19/D46*\n')
        out.append('%ADD90C,0.0100*%\n')
        out.append('%ADD91C,0.1570X0.1330*%\n')
        out.append('%ADD92C,0.0900X0.0660*%\n')
        out.append('%ADD93C,0.1770X0.1530*%\n')
        out.append('%ADD94C,0.1000X0.0760*%\n')


def convert(sources, outpath, layer_name, function=None):
    """Plain positive conversion; multiple sources appended in order."""
    all_cmds = [parse_spl(p) for p in sources]
    used = sorted({c[1] for cmds in all_cmds for c in cmds if c[0] == 'select'})
    out = []
    src_desc = ' + '.join(s.split('/')[-1] for s in sources)
    header(out, layer_name, src_desc, function, used)
    out.append('%LPD*%\n')
    out.append('G01*\n')
    for i, cmds in enumerate(all_cmds):
        if len(all_cmds) > 1:
            out.append(f'G04 --- begin {sources[i].split("/")[-1]} ---*\n')
        emit_body(out, cmds, sources[i])
    out.append('M02*\n')
    with open(outpath, 'w') as f:
        f.writelines(out)
    return used


def convert_plane(neg_src, pad_src, outpath, layer_name, function=None):
    """Composite plane layer.

    The original artwork is a negative-plane pair:
      - neg_src (SPARL2/SPARL5): clearances -- antipads, isolation channels
        around embedded traces, board outline channel, flood frame
      - pad_src (SPARL2A/SPARL5A): pads, printed dark on top, restoring
        the pad annulus inside each antipad
    Composite: flood dark -> neg_src clear -> pad_src dark.
    """
    neg = parse_spl(neg_src)
    pad = parse_spl(pad_src)
    used = sorted({c[1] for c in neg + pad if c[0] == 'select'})
    out = []
    src_desc = f'{neg_src.split("/")[-1]} (clear) + {pad_src.split("/")[-1]} (dark)'
    header(out, layer_name, src_desc, function, used, extra_comments=(
        'Original artwork is a negative-plane pair; rebuilt here as a',
        'positive composite: solid flood (dark), then '
        + neg_src.split('/')[-1] + ' clearances (LPC),',
        'then ' + pad_src.split('/')[-1] + ' pads (LPD). Pads without an antipad in',
        'the clear pass connect directly to the plane (no thermal relief),',
        'matching the original film composite.',
    ))
    out.append('G01*\n')
    # Pass 1: flood
    x0, y0, x1, y1 = FLOOD_RECT
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    out.append('G04 Pass 1: plane flood over the original photoplot frame*\n')
    out.append('%LPD*%\n')
    out.append('G36*\n')
    for i, (x, y) in enumerate(pts):
        xo = (x + OFF_X) * 10
        yo = (y + OFF_Y) * 10
        out.append(f'X{xo}Y{yo}D0{2 if i == 0 else 1}*\n')
    out.append('G37*\n')
    out.append(f'G04 Pass 2: clearances from {neg_src.split("/")[-1]}*\n')
    out.append('%LPC*%\n')
    emit_body(out, neg, neg_src)
    out.append(f'G04 Pass 3: pads from {pad_src.split("/")[-1]}*\n')
    out.append('%LPD*%\n')
    emit_body(out, pad, pad_src)
    out.append('M02*\n')
    with open(outpath, 'w') as f:
        f.writelines(out)
    return used


if __name__ == '__main__':
    import os
    src = 'source/Sparrow'
    dst = 'gerbers/'
    os.makedirs(dst, exist_ok=True)
    os.makedirs(f'{dst}/original-polarity', exist_ok=True)

    plain = [
        (['SPARL1.SPL'], 'falcon-rev4-L1-copper-top.gbr', 'Copper layer 1 (component side)', 'Copper,L1,Top,Signal'),
        (['SPARL3.SPL'], 'falcon-rev4-L3-copper-inner.gbr', 'Copper layer 3 (int signal 1)', 'Copper,L3,Inr,Signal'),
        (['SPARL4.SPL'], 'falcon-rev4-L4-copper-inner.gbr', 'Copper layer 4 (int signal 2)', 'Copper,L4,Inr,Signal'),
        (['SPARL6.SPL'], 'falcon-rev4-L6-copper-bottom.gbr', 'Copper layer 6 (solder side)', 'Copper,L6,Bot,Signal'),
        (['SPARSM1.SPL'], 'falcon-rev4-soldermask-top.gbr', 'Solder mask, component side', 'Soldermask,Top'),
        (['SPARSM2.SPL'], 'falcon-rev4-soldermask-bottom.gbr', 'Solder mask, solder side', 'Soldermask,Bot'),
        (['SPARSS1.SPL'], 'falcon-rev4-silkscreen-top.gbr', 'Silkscreen, component side', 'Legend,Top'),
        (['SPARSS2.SPL'], 'falcon-rev4-silkscreen-bottom.gbr', 'Silkscreen, solder side', 'Legend,Bot'),
        # verbatim positive-polarity conversions of the raw negative artwork
        (['SPARL2.SPL'],  'original-polarity/falcon-rev4-L2-clearances.gbr',  'Layer 2 PWR plane, clearance artwork (originally negative)', None),
        (['SPARL2A.SPL'], 'original-polarity/falcon-rev4-L2A-pads.gbr', 'Layer 2 PWR plane, pad artwork', None),
        (['SPARL5.SPL'],  'original-polarity/falcon-rev4-L5-clearances.gbr',  'Layer 5 GND plane, clearance artwork (originally negative)', None),
        (['SPARL5A.SPL'], 'original-polarity/falcon-rev4-L5A-pads.gbr', 'Layer 5 GND plane, pad artwork', None),
    ]
    for srcs, name, desc, func in plain:
        used = convert([f'{src}/{s}' for s in srcs], f'{dst}/{name}', desc, func)
        print(f'{name}: apertures {used}')

    planes = [
        ('SPARL2.SPL', 'SPARL2A.SPL', 'falcon-rev4-L2-copper-inner-pwr-plane.gbr', 'Copper layer 2 (PWR plane with embedded traces)', 'Copper,L2,Inr,Mixed'),
        ('SPARL5.SPL', 'SPARL5A.SPL', 'falcon-rev4-L5-copper-inner-gnd-plane.gbr', 'Copper layer 5 (GND plane with embedded traces)', 'Copper,L5,Inr,Mixed'),
    ]
    for n, p, name, desc, func in planes:
        used = convert_plane(f'{src}/{n}', f'{src}/{p}', f'{dst}/{name}', desc, func)
        print(f'{name}: apertures {used}')

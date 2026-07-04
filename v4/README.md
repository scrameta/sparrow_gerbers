# Atari Falcon rev4 ("Sparrow") — RS-274X conversion

Conversion of the original Seetrax RANGER RS-274-D photoplot files
(`SPAR*.SPL`, Gerber 6000/6200 dialect) to modern RS-274X.

## Source format (from SPARROW.USR)

- Absolute imperial coordinates, 5.3 format (units of 0.001"), leading
  zeros omitted, D codes modal, no G codes, no arcs.
- Aperture wheel defined in the SPARROW.USR symbol table, positions
  10–80: shape 1 = round, shape 2 = square, shape 3 (draw-only) treated
  as round, positions 19/46 = moiré registration targets.

## Output format

- `%FSLAX24Y24*%` `%MOIN*%` (2.4 inch format, units of 0.0001").
  All source coordinates are integer mils, so the conversion is exact.
- Every coordinate block carries an explicit D01/D02/D03 (modal D codes
  from the source resolved; coordinate-only blocks only ever followed
  D01/D02 in the source, so resolution is unambiguous).
- All coordinates translated by **(−4849, −7746) mil** so the image
  lands in the same frame as `Drill_PTH.drl` (rev2 KiCad coordinate
  frame). Verified: 3766 of 3873 drill hits land exactly (to the mil)
  on inner-layer pad flash centres; the remainder are the known
  drawn-pad locations.
- Leading/trailing photoplotter park moves to (0,0) dropped (they plot
  nothing and only distort viewers' bounding boxes).

## Layer set

| File | Source | PDF page |
|------|--------|----------|
| falcon-rev4-L1-copper-top.gbr | SPARL1 | 8 |
| falcon-rev4-L2-copper-inner-pwr-plane.gbr | SPARL2 + SPARL2A (composite) | 7 |
| falcon-rev4-L3-copper-inner.gbr | SPARL3 | 6 |
| falcon-rev4-L4-copper-inner.gbr | SPARL4 | 5 |
| falcon-rev4-L5-copper-inner-gnd-plane.gbr | SPARL5 + SPARL5A (composite) | 4 |
| falcon-rev4-L6-copper-bottom.gbr | SPARL6 | 3 |
| falcon-rev4-soldermask-top.gbr | SPARSM1 | 9 |
| falcon-rev4-soldermask-bottom.gbr | SPARSM2 | 2 |
| falcon-rev4-silkscreen-top.gbr | SPARSS1 | 10 |
| falcon-rev4-silkscreen-bottom.gbr | SPARSS2 | 1 |

(The reference PDF pages run bottom-of-stack to top.)

## The plane layers (L2 PWR, L5 GND)

The 2/2A and 5/5A pairs are **negative-plane artwork**, not two halves
of a positive image:

- **SPARL2 / SPARL5** contain the *clearances*: antipads (a larger
  aperture flashed at each isolated hole), the isolation channels drawn
  either side of / around embedded traces, connector slot clearances,
  the stepped board-outline channel, and the photoplot frame rectangle
  (4950,8150)–(23050,20150) in the original frame.
- **SPARL2A / SPARL5A** contain the *pads*: one flash per plated hole
  (3823, the same padstack as L3/L4), printed dark **on top of** the
  clearances.

The composite that reproduces the film is therefore a three-pass
sandwich, which is exactly what the converted files contain:

1. `%LPD*%` — solid G36/G37 flood over the original photoplot frame;
2. `%LPC*%` — the entire SPARL2/SPARL5 content as clear;
3. `%LPD*%` — the entire SPARL2A/SPARL5A content as dark.

Result per hole: pads with an antipad in pass 2 end up as a pad inside
an annular isolation ring (e.g. 50 mil pad in a 70 mil antipad = 10 mil
ring). Holes with **no** antipad — 319 on L2 (PWR), 769 on L5 (GND) —
connect directly to the plane with no thermal relief, matching the
original composite. Every antipad flash in L2/L5 sits exactly on a pad
flash centre in L2A/L5A (3504/3504 and 3054/3054).

`original-polarity/` contains verbatim positive-polarity conversions of
the four raw files for reference/archival purposes.

## Registration targets

The photohead "moiré with cross" targets (D19 = 157 mil, D46 = 177 mil,
flashed at three plot corners) are decomposed into standard apertures
(two annuli as circles-with-holes, D90–D94, plus a 10 mil crosshair
drawn with D90) rather than aperture macros. The moiré macro primitive
is deprecated in the current Gerber spec, and gerbv miscomposites *any*
macro aperture flashed with clear polarity, which matters inside the
plane sandwiches. The decomposition uses nothing but standard C
apertures and renders identically everywhere.

## Verification

Each converted layer was rasterised (gerbv) and compared against the
corresponding page of `falcon-rev4-board.pdf`:

- L2 composite vs page 7: Jaccard 0.963; L5 composite vs page 4: 0.968.
- Signal/mask layers: 0.72–0.80 raw Jaccard (differences are purely
  stroke-width rasterisation).
- Silkscreens: 99.9–100 % mutual containment within a 2-pixel dilation
  (raw Jaccard is low only because stroked text is width-sensitive).
- A regional 8×12 disagreement grid over the plane layers shows a
  uniform 1–8 % residual with no structural hotspots.
- All files parse cleanly in gerbonara as a second, independent parser,
  and load in gerbv. (gerbv ≤2.9 warns about the `%TF.FileFunction`
  X2 attributes; the warning is harmless. Strip the `%TF` lines if a
  very old tool refuses them.)

Conversion script: `convert.py` (deterministic, re-runnable against the
original `Sparrow/` directory).

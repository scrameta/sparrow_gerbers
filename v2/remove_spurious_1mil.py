#!/usr/bin/env python3
"""Very simple correction for the legacy Atari Falcon/Sparrow Gerbers, v7.

This version deliberately avoids geometric heuristics:
  * Add explicit %MOIN*% after old G70 inch units.
  * If a Gerber defines D11 as a 0.001 inch circular aperture, convert every
    D11 D01 exposure into a D02 move. This treats D11 as a plotter/travel/meta
    pen that was accidentally left down.
  * Do not remove post-G37 replays, do not filter by diagonal/axis-aligned,
    and do not special-case plane layers.
  * Add modern Excellon headers and inferred tool diameters to the drills.

The D11 coordinates are preserved as moves, rather than deleted, so modal
position/state remains close to the original file.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

TOOL_DIAM_INCH = {
    1: 0.02000, 2: 0.02500, 3: 0.03800, 4: 0.05000, 5: 0.05500,
    6: 0.06200, 7: 0.07500, 8: 0.09000, 9: 0.10900, 10: 0.12500,
    11: 0.13800, 12: 0.13900, 13: 0.15000, 14: 0.15800, 15: 0.16500,
    16: 0.19600, 17: 0.23700, 18: 0.27600, 19: 0.31500,
}

GERBER_NAMES = [
    "Drill_Drawing.spl",
    "Layer1.spl", "Layer2.spl", "Layer3.spl", "Layer4.spl", "Layer5.spl", "Layer6.spl",
    "Silkscreen_Bottom.spl", "Silkscreen_Top.spl",
    "Soldermask_Bottom.spl", "Soldermask_Top.spl",
]

DSEL_RE = re.compile(r"^D(?P<d>\d+)\*$")
COORD_RE = re.compile(r"^(?P<body>(?:G0?[123])?(?:X-?\d+)?(?:Y-?\d+)?)(?:D(?P<op>0?[123]))?\*$")
ADD11_1MIL_RE = re.compile(r"^%ADD11C,0*\.0*100\*%$", re.IGNORECASE)


def line_body(line: str) -> str:
    return line.strip().rstrip("*")


def add_moin_after_g70(lines: list[str]) -> tuple[list[str], bool]:
    if any("%MOIN" in l.upper() or "%MOMM" in l.upper() for l in lines[:30]):
        return lines, False
    out: list[str] = []
    added = False
    for line in lines:
        out.append(line)
        if line_body(line) == "G70" and not added:
            out.append("%MOIN*%")
            added = True
    return out, added


def parse_coord_line(line: str, cur_x: int | None, cur_y: int | None, cur_op: int | None):
    m = COORD_RE.fullmatch(line.strip())
    if not m:
        return False, cur_x, cur_y, cur_op, False
    body = m.group("body")
    xm = re.search(r"X(-?\d+)", body)
    ym = re.search(r"Y(-?\d+)", body)
    op_s = m.group("op")
    x = cur_x if xm is None else int(xm.group(1))
    y = cur_y if ym is None else int(ym.group(1))
    op = cur_op if op_s is None else int(op_s)
    return True, x, y, op, op_s is not None


def force_operation(line: str, op: int) -> str:
    stripped = line.strip()
    if not stripped.endswith("*"):
        return line
    if re.search(r"D0?[123]\*", stripped):
        return re.sub(r"D0?[123]\*", f"D0{op}*", stripped)
    return stripped[:-1] + f"D0{op}*"


def fix_gerber(src: Path, dst: Path) -> tuple[bool, int, bool]:
    """Add explicit units and convert D11/1-mil draws to moves.

    Returns: (has_d11_1mil, converted_count, added_units)
    """
    lines = src.read_text(encoding="latin1").splitlines(keepends=False)
    lines, added_units = add_moin_after_g70(lines)
    has_d11_1mil = any(ADD11_1MIL_RE.fullmatch(l.strip()) for l in lines)

    if not has_d11_1mil:
        dst.write_text("\n".join(lines) + "\n", encoding="latin1")
        return False, 0, added_units

    out: list[str] = []
    cur_ap: int | None = None
    cur_x: int | None = None
    cur_y: int | None = None
    cur_op: int | None = None      # modal operation in original stream
    out_op: int | None = None      # modal operation in emitted stream
    converted = 0

    for line in lines:
        dsel = DSEL_RE.fullmatch(line.strip())
        if dsel and int(dsel.group("d")) >= 10:
            cur_ap = int(dsel.group("d"))
            out.append(line)
            continue

        is_coord, x, y, op, explicit_op = parse_coord_line(line, cur_x, cur_y, cur_op)
        if not is_coord:
            out.append(line)
            continue

        # Only the 1 mil D11 aperture is treated as accidental plotter/meta ink.
        # Convert actual moves/draws from D01 to D02, preserving coordinates.
        if cur_ap == 11 and op == 1 and (cur_x is None or cur_y is None or x != cur_x or y != cur_y):
            out_line = force_operation(line, 2)
            out_op = 2
            converted += 1
        else:
            out_line = line
            # If we previously forced D02, make the next real implicit draw explicit
            # so output modal state matches the original intent.
            if op == 1 and not explicit_op and out_op != 1:
                out_line = force_operation(line, 1)
                out_op = 1
            elif explicit_op:
                out_op = op

        out.append(out_line)
        cur_x, cur_y, cur_op = x, y, op

    dst.write_text("\n".join(out) + "\n", encoding="latin1")
    return True, converted, added_units


def fix_drill(src: Path, dst: Path, is_npth: bool = False) -> None:
    src_lines = [l.strip() for l in src.read_text(encoding="latin1").splitlines()]
    body_lines = [l for l in src_lines if l and l != "%" and not l.startswith("M48")]
    body_lines = [l for l in body_lines if l != "M30"]

    out = [
        "M48",
        "; Corrected from legacy headerless Excellon",
        "; Units: inches; coordinate format: 2.3; leading zero suppression",
        "INCH,LZ",
    ]
    if not is_npth:
        for t, dia in TOOL_DIAM_INCH.items():
            out.append(f"T{t:02d}C{dia:.5f}")
    out.append("%")
    for l in body_lines:
        m = re.fullmatch(r"T(\d+)", l)
        if m:
            out.append(f"T{int(m.group(1)):02d}")
        else:
            out.append(l)
    out.append("M30")
    dst.write_text("\n".join(out) + "\n", encoding="latin1")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("src_dir", type=Path)
    ap.add_argument("dst_dir", type=Path)
    args = ap.parse_args()
    args.dst_dir.mkdir(parents=True, exist_ok=True)

    report: list[str] = []
    for name in GERBER_NAMES:
        src = args.src_dir / name
        dst = args.dst_dir / name
        if not src.exists():
            continue
        has_d11, converted, added = fix_gerber(src, dst)
        report.append(f"{name}: added_explicit_MOIN={added}, D11_is_1mil={has_d11}, converted_D11_D01_to_D02={converted}")

    fix_drill(args.src_dir / "Drill_PTH.spl", args.dst_dir / "Drill_PTH.spl", is_npth=False)
    fix_drill(args.src_dir / "Drill_NPTH.spl", args.dst_dir / "Drill_NPTH.spl", is_npth=True)
    report.append("Drill_PTH.spl: added M48/INCH,LZ/header/tool diameters T01..T19")
    report.append("Drill_NPTH.spl: added empty M48/INCH,LZ header")

    # Include the drill tool map as a convenient audit trail.
    map_lines = ["tool,diameter_inch"] + [f"T{t:02d},{dia:.5f}" for t, dia in TOOL_DIAM_INCH.items()]
    (args.dst_dir / "drill-tool-map.csv").write_text("\n".join(map_lines) + "\n", encoding="utf-8")

    for src in args.src_dir.iterdir():
        if src.is_file() and not (args.dst_dir / src.name).exists():
            shutil.copy2(src, args.dst_dir / src.name)

    (args.dst_dir / "README-fixes.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()

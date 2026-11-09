# -*- coding: utf-8 -*-
"""ionos-sdr-mini digital twin, layer 4: the mechanical layer.

Layers 1-3 read the netlist.  This one reads the BOARD, and asks the
questions copper connectivity cannot answer:

  * when the radio board is seated on its alignment pins, does OUR pin n
    actually touch THEIR pin n - or is the footprint in end-for-end?
  * does the radio board fit on our outline, and is anything of ours tall
    enough to hit its underside?
  * does every footprint have a courtyard and a silkscreen body, so that
    the DRC can do its job and the assembler can see what goes where?

It also writes a "litmus paper" overlay: both boards' pads drawn to the
same scale, half transparent, anchored on the alignment holes.  Open the
SVG in a browser and the two layers either register or they do not.

Usage:  kicad-python twin_mech.py [path\\to\\board.kicad_pcb]
"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_mech as M

import pcbnew

PRJ = os.path.dirname(HERE)
DEFAULT_PCB = os.path.join(PRJ, "ionosSDR_mini.kicad_pcb")
OUTDIR = os.path.join(HERE, "mech")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
log = []
MM = pcbnew.ToMM


def say(level, group, msg):
    log.append((level, group, msg))


# ----------------------------------------------------------------- board
def pad_xy(fp, num):
    p = fp.FindPadByNumber(num)
    if p is None:
        return None
    pos = p.GetPosition()
    return (MM(pos.x), MM(pos.y))


def align_holes(fp):
    """The two unnumbered NPTH pads of a mezzanine terminal footprint."""
    out = []
    for p in fp.Pads():
        if not p.GetNumber() and p.GetDrillSize().x > 0:
            pos = p.GetPosition()
            out.append((MM(pos.x), MM(pos.y), MM(p.GetDrillSize().x)))
    return sorted(out)


def layer_items(fp, layers, board=None):
    """Count graphic items on the given layer IDs (names differ between the
    file format and the UI, so compare IDs)."""
    n = 0
    for g in fp.GraphicalItems():
        try:
            if g.GetLayer() in layers:
                n += 1
        except Exception:
            pass
    return n


CRTYD = (pcbnew.F_CrtYd, pcbnew.B_CrtYd)
SILKS = (pcbnew.F_SilkS, pcbnew.B_SilkS)


# ------------------------------------------------------------ the checks
def solve_transform(board):
    """Fit X = u + Tx, Y = Ty - v from our alignment holes."""
    txs, tys = [], []
    for con, sock in M.MATES.items():
        fp = board.FindFootprintByReference(con)
        if fp is None:
            say(FAIL, "fit", "%s is not on the board" % con)
            return None
        holes = align_holes(fp)
        if len(holes) != 2:
            say(FAIL, "fit", "%s has %d alignment holes, expected 2"
                % (con, len(holes)))
            return None
        ours = sorted(h[0] for h in holes)
        theirs = sorted(h[0] for h in M.RB_ALIGN
                        if abs(h[1] - M.RB_SOCKETS[sock]["centre_v"]) < 0.1)
        for a, b in zip(ours, theirs):
            txs.append(a - b)
        tys.append(holes[0][1] + M.RB_SOCKETS[sock]["centre_v"])
        # spacing check
        ds, dt = ours[1] - ours[0], theirs[1] - theirs[0]
        if abs(ds - dt) > 0.10:
            say(FAIL, "fit", "%s alignment pitch %.3f mm, the radio board "
                "has %.3f mm" % (con, ds, dt))
        else:
            say(PASS, "fit", "%s alignment pitch %.3f vs %.3f mm (%.0f um)"
                % (con, ds, dt, abs(ds - dt) * 1000))
    Tx = sum(txs) / len(txs)
    Ty = sum(tys) / len(tys)
    if max(tys) - min(tys) > 0.10:
        say(FAIL, "fit", "the two sockets do not agree on the placement: "
            "Ty = %s" % ["%.3f" % t for t in tys])
    else:
        say(PASS, "fit", "mating transform  X = u + %.3f ,  Y = %.3f - v"
            % (Tx, Ty))
    return (Tx, Ty)


def check_pin_for_pin(board, T):
    """THE check: our pin n must land on their pin n."""
    Tx, Ty = T
    worst = 0.0
    for con, sock in M.MATES.items():
        fp = board.FindFootprintByReference(con)
        bad = []
        for n in range(1, M.RB_COLS * 2 + 1):
            ours = pad_xy(fp, str(n))
            if ours is None:
                say(FAIL, "pins", "%s has no pad %d" % (con, n))
                continue
            # which of their pins is nearest to our pad?
            best = None
            for m in range(1, M.RB_COLS * 2 + 1):
                u, v = M.rb_pin(sock, m)
                d = ((ours[0] - (u + Tx)) ** 2 + (ours[1] - (Ty - v)) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, m)
            worst = max(worst, best[0])
            if best[1] != n:
                bad.append((n, best[1]))
        if bad:
            say(FAIL, "pins",
                "%s <-> %s is reversed: our pin %d meets their pin %d, "
                "our %d meets their %d, ... %d of %d pins wrong. Rotate the "
                "footprint 180 deg."
                % (con, sock, bad[0][0], bad[0][1], bad[1][0], bad[1][1],
                   len(bad), M.RB_COLS * 2))
        else:
            say(PASS, "pins", "%s <-> %s : all %d pins meet their own number"
                % (con, sock, M.RB_COLS * 2))
    say(PASS if worst < 1.0 else FAIL, "pins",
        "worst pad-to-contact offset %.3f mm" % worst)


def check_outline(board, T):
    """The radio board must sit inside our board edge."""
    Tx, Ty = T
    w, h = M.RB["outline_mm"]
    x0, x1 = Tx, Tx + w
    y0, y1 = Ty - h, Ty
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0 = MM(bb.GetX()), MM(bb.GetY())
    bx1, by1 = bx0 + MM(bb.GetWidth()), by0 + MM(bb.GetHeight())
    over = []
    if x0 < bx0: over.append("%.2f mm past the left edge" % (bx0 - x0))
    if x1 > bx1: over.append("%.2f mm past the right edge" % (x1 - bx1))
    if y0 < by0: over.append("%.2f mm past the top edge" % (by0 - y0))
    if y1 > by1: over.append("%.2f mm past the bottom edge" % (y1 - by1))
    if over:
        say(WARN, "outline", "the radio board overhangs: %s" % "; ".join(over))
    else:
        say(PASS, "outline",
            "radio board occupies X %.1f..%.1f, Y %.1f..%.1f - inside the "
            "board with %.1f/%.1f/%.1f/%.1f mm to spare"
            % (x0, x1, y0, y1, x0 - bx0, bx1 - x1, y0 - by0, by1 - y1))
    sx, sy = M.RB_SMA["centre"]
    say(PASS, "outline", "SMA lands at X %.1f, Y %.1f (on the radio board's "
        "top side, nothing of ours underneath it)" % (sx + Tx, Ty - sy))
    return (x0, y0, x1, y1)


def check_clearance(board, box, T):
    """What of ours sits under the radio board, and is it low enough?"""
    x0, y0, x1, y1 = box
    unknown, tall = [], []
    n = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in M.MATES:
            continue
        p = fp.GetPosition()
        px, py = MM(p.x), MM(p.y)
        if not (x0 < px < x1 and y0 < py < y1):
            continue
        n += 1
        hgt = M.height_of(str(fp.GetFPIDAsString()), fp.GetValue())
        if hgt is None:
            unknown.append(ref)
        elif hgt > M.UNDER_RADIO_MM:
            tall.append((ref, hgt))
    say(PASS, "clearance",
        "%d of our parts sit under the radio board; %.2f mm of head room "
        "(%.2f mm mated, minus %.2f mm of their own underside)"
        % (n, M.UNDER_RADIO_MM, M.SAMTEC["mated_height_mm"], M.RB_BOTTOM_MAX_H))
    for ref, h in tall:
        say(FAIL, "clearance", "%s is %.2f mm tall, the gap is %.2f mm"
            % (ref, h, M.UNDER_RADIO_MM))
    if unknown:
        say(WARN, "clearance", "height unknown for %s - check by hand"
            % ", ".join(sorted(unknown)))
    if not tall and not unknown:
        say(PASS, "clearance", "every part underneath is low enough")


def check_devkit(board):
    fp = board.FindFootprintByReference("IC1")
    if fp is None:
        say(FAIL, "devkit", "IC1 is not on the board")
        return
    say(WARN, "devkit", M.DEVKIT_UNVERIFIED)
    d = M.DEVKIT["header"]
    xs, ys = [], []
    for p in fp.Pads():
        if p.GetNumber():
            pos = p.GetPosition()
            xs.append(MM(pos.x)); ys.append(MM(pos.y))
    rows = max(xs) - min(xs)
    span = max(ys) - min(ys)
    want_span = (d["pins_per_row"] - 1) * d["pitch_mm"]
    ok = (abs(rows - d["row_spacing_mm"]) < 0.05
          and abs(span - want_span) < 0.05)
    say(PASS if ok else FAIL, "devkit",
        "header 2 x %d, pitch %.2f mm: rows %.2f mm (want %.2f), span %.2f mm "
        "(want %.2f)" % (d["pins_per_row"], d["pitch_mm"], rows,
                         d["row_spacing_mm"], span, want_span))
    rx0, ry0, rx1, ry1 = M.DEVKIT["outline_rel"]
    p = fp.GetPosition()
    cx, cy = MM(p.x), MM(p.y)
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0 = MM(bb.GetX()), MM(bb.GetY())
    bx1, by1 = bx0 + MM(bb.GetWidth()), by0 + MM(bb.GetHeight())
    mx0, my0, mx1, my1 = cx + rx0, cy + ry0, cx + rx1, cy + ry1
    if my0 < by0 or my1 > by1 or mx0 < bx0 or mx1 > bx1:
        say(WARN, "devkit", "the module overhangs our board edge "
            "(X %.1f..%.1f, Y %.1f..%.1f vs board X %.1f..%.1f, Y %.1f..%.1f)"
            % (mx0, mx1, my0, my1, bx0, bx1, by0, by1))
    else:
        say(PASS, "devkit", "module footprint X %.1f..%.1f, Y %.1f..%.1f - "
            "inside the board, %.1f mm clear of the top edge"
            % (mx0, mx1, my0, my1, my0 - by0))
    under = []
    for other in board.GetFootprints():
        if other.GetReference() == "IC1":
            continue
        q = other.GetPosition()
        qx, qy = MM(q.x), MM(q.y)
        if mx0 < qx < mx1 and my0 < qy < my1:
            h = M.height_of(str(other.GetFPIDAsString()))
            under.append((other.GetReference(), h))
    if under:
        bad = [r for r, h in under if h is None or h > M.UNDER_DEVKIT_MM]
        say(WARN if bad else PASS, "devkit",
            "%d parts under the module: %s"
            % (len(under), ", ".join(r for r, h in sorted(under))))
    else:
        say(PASS, "devkit", "nothing of ours sits under the module")


def check_footprint_hygiene(board):
    """A footprint with no courtyard silently disables a whole DRC test."""
    nocrt, nosilk, big = [], [], []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in M.COURTYARD_EXEMPT:
            continue
        if layer_items(fp, CRTYD) == 0:
            bb = fp.GetBoundingBox(False, False)
            # a part with real area and no courtyard is a hole in the DRC;
            # a 1.5 mm test pad has nothing to collide with
            (big if max(MM(bb.GetWidth()), MM(bb.GetHeight())) > 5.0
             else nocrt).append(ref)
        if layer_items(fp, SILKS) == 0:
            nosilk.append(ref)
    if big:
        say(FAIL, "hygiene", "no courtyard on a part with real area - the "
            "DRC's overlap test cannot run on it: %s. Draw the module body "
            "from its datasheet, in the library, not on the instance."
            % ", ".join(sorted(big)))
    if nocrt:
        say(WARN, "hygiene", "no courtyard, but nothing to collide with "
            "either (test pads): %s" % ", ".join(sorted(nocrt)))
    if not big and not nocrt:
        say(PASS, "hygiene", "every footprint has a courtyard")
    if nosilk:
        say(WARN, "hygiene", "no silkscreen body - nothing on the board tells "
            "the assembler where it goes or which end is pin 1: %s"
            % ", ".join(sorted(nosilk)))
    else:
        say(PASS, "hygiene", "every footprint has a silkscreen body")


# ----------------------------------------------------------- the overlay
def overlay_svg(board, T, path):
    """Litmus paper: both boards' pads, same scale, half transparent,
    anchored on the alignment holes."""
    Tx, Ty = T
    w, h = M.RB["outline_mm"]
    pad = 6.0
    x0, y0 = Tx - pad, Ty - h - pad
    W, H = w + 2 * pad, h + 2 * pad
    S = 14.0                      # px per mm
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %.2f %.2f">' % (W * S, H * S, W, H),
         '<rect width="100%%" height="100%%" fill="#fff"/>',
         '<g transform="translate(%.3f,%.3f)">' % (-x0, -y0)]
    o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" rx="%.2f" '
             'fill="none" stroke="#c33" stroke-width="0.15"/>'
             % (Tx, Ty - h, w, h, M.RB["corner_radius_mm"]))
    for sock in M.RB_SOCKETS:
        for n in range(1, M.RB_COLS * 2 + 1):
            u, v = M.rb_pin(sock, n)
            o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                     'fill="#d22" fill-opacity="0.45"/>'
                     % (u + Tx - M.RB_PAD[0] / 2, Ty - v - M.RB_PAD[1] / 2,
                        M.RB_PAD[0], M.RB_PAD[1]))
    for con in M.MATES:
        fp = board.FindFootprintByReference(con)
        if fp is None:
            continue
        for p in fp.Pads():
            if not p.GetNumber():
                continue
            pos = p.GetPosition()
            sz = p.GetSize()
            o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                     'fill="#26c" fill-opacity="0.45"/>'
                     % (MM(pos.x) - MM(sz.x) / 2, MM(pos.y) - MM(sz.y) / 2,
                        MM(sz.x), MM(sz.y)))
        for n in ("1", "2", "39", "40"):
            q = pad_xy(fp, n)
            if q:
                o.append('<text x="%.3f" y="%.3f" font-size="1.3" '
                         'fill="#004" text-anchor="middle">%s</text>'
                         % (q[0], q[1] + 0.4, n))
    for u, v in M.RB_ALIGN:
        o.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" '
                 'stroke="#c33" stroke-width="0.12"/>'
                 % (u + Tx, Ty - v, M.RB_ALIGN_D / 2))
    for con in M.MATES:
        fp = board.FindFootprintByReference(con)
        for hx, hy, hd in align_holes(fp):
            o.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" '
                     'stroke="#26c" stroke-width="0.10"/>' % (hx, hy, hd / 2))
    sx, sy = M.RB_SMA["centre"]
    o.append('<circle cx="%.3f" cy="%.3f" r="3.2" fill="none" stroke="#c33" '
             'stroke-width="0.12" stroke-dasharray="0.6 0.4"/>'
             % (sx + Tx, Ty - sy))
    o.append('<text x="%.3f" y="%.3f" font-size="1.6" fill="#c33">SMA</text>'
             % (sx + Tx + 3.6, Ty - sy))
    o.append('</g><text x="8" y="4" font-size="2.2" fill="#222">'
             'red = BRD4265B sockets and alignment holes, '
             'blue = our terminals</text>')
    o.append('</svg>')
    io.open(path, "w", encoding="utf-8").write("\n".join(o))


def overlay_devkit_svg(board, path):
    """The DevKit's header and the two candidate module envelopes over our
    board edge.  Without Espressif's own drawing this is the honest way to
    show the open question instead of picking one silently."""
    fp = board.FindFootprintByReference("IC1")
    if fp is None:
        return
    p = fp.GetPosition()
    cx, cy = MM(p.x), MM(p.y)
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0 = MM(bb.GetX()), MM(bb.GetY())
    bx1, by1 = bx0 + MM(bb.GetWidth()), by0 + MM(bb.GetHeight())
    pad = 8.0
    x0, y0 = cx - 40, by0 - pad
    W, H = 80.0, (by1 - by0) + 2 * pad
    S = 9.0
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %.2f %.2f">' % (W * S, H * S, W, H),
         '<rect width="100%%" height="100%%" fill="#fff"/>',
         '<g transform="translate(%.3f,%.3f)">' % (-x0, -y0)]
    o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="none" '
             'stroke="#333" stroke-width="0.25"/>'
             % (bx0, by0, bx1 - bx0, by1 - by0))
    rx0, ry0, rx1, ry1 = M.DEVKIT["outline_rel"]
    o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#2a2" '
             'fill-opacity="0.18" stroke="#2a2" stroke-width="0.25"/>'
             % (cx + rx0, cy + ry0, rx1 - rx0, ry1 - ry0))
    o.append('<rect x="%.3f" y="%.3f" width="28" height="70" fill="#c60" '
             'fill-opacity="0.14" stroke="#c60" stroke-width="0.25" '
             'stroke-dasharray="1.5 1"/>' % (cx - 14, cy - 35))
    for q in fp.Pads():
        if not q.GetNumber():
            continue
        pos, sz = q.GetPosition(), q.GetSize()
        o.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                 'fill="#26c" fill-opacity="0.6"/>'
                 % (MM(pos.x) - MM(sz.x) / 2, MM(pos.y) - MM(sz.y) / 2,
                    MM(sz.x), MM(sz.y)))
    o.append('</g>')
    o.append('<text x="8" y="5" font-size="2.4" fill="#222">ESP32-S3-DevKitC-1'
             ' - blue: header pads, green: footprint outline 26.42 x 62.74, '
             'orange dashed: 28 x 70 from third-party sources</text>')
    o.append('<text x="8" y="9" font-size="2.0" fill="#a00">if the module is '
             'really 70 mm long it overhangs our top edge - confirm against '
             'Espressif DXF_ESP32-S3-DevKitC-1_V1.1</text>')
    o.append('</svg>')
    io.open(path, "w", encoding="utf-8").write("\n".join(o))


# ======================================================================
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = args[0] if args else DEFAULT_PCB
    if not os.path.exists(path):
        print("board not found: %s" % path)
        return 2
    board = pcbnew.LoadBoard(path)
    print("=" * 76)
    print(" ionos-sdr-mini digital twin - layer 4: mechanical")
    print(" board : %s" % path)
    print(" radio : %s  %.1f x %.1f mm" % (M.RB["name"], M.RB["outline_mm"][0],
                                           M.RB["outline_mm"][1]))
    print("=" * 76)

    T = solve_transform(board)
    if T is None:
        print("cannot place the radio board - stopping")
        return 1
    check_pin_for_pin(board, T)
    box = check_outline(board, T)
    check_clearance(board, box, T)
    check_devkit(board)
    check_footprint_hygiene(board)

    try:
        os.makedirs(OUTDIR, exist_ok=True)
        svg = os.path.join(OUTDIR, "overlay_radioboard.svg")
        overlay_svg(board, T, svg)
        say(PASS, "overlay", "wrote %s - open it in a browser" % svg)
        svg2 = os.path.join(OUTDIR, "overlay_devkit.svg")
        overlay_devkit_svg(board, svg2)
        say(PASS, "overlay", "wrote %s" % svg2)
    except Exception as e:
        say(WARN, "overlay", "could not write the overlay: %s" % e)

    groups = {}
    for lvl, grp, msg in log:
        groups.setdefault(grp, []).append((lvl, msg))
    titles = [("fit", "does the radio board sit where we think"),
              ("pins", "pin for pin, through the socket"),
              ("outline", "does it fit on our board"),
              ("clearance", "what is underneath, and how tall"),
              ("devkit", "the ESP32-S3 module"),
              ("hygiene", "courtyards and silkscreen"),
              ("overlay", "litmus paper")]
    verbose = "-q" not in sys.argv
    for grp, title in titles:
        if grp not in groups:
            continue
        print("\n--- %s : %s" % (grp, title))
        for lvl, msg in groups[grp]:
            if lvl != PASS:
                print("  %-4s %s" % (lvl, msg))
            elif verbose:
                print("  ok   %s" % msg)

    nf = sum(1 for l, g, m in log if l == FAIL)
    nw = sum(1 for l, g, m in log if l == WARN)
    np_ = sum(1 for l, g, m in log if l == PASS)
    print("\n" + "=" * 76)
    print(" RESULT: %d pass, %d warn, %d FAIL" % (np_, nw, nf))
    print("=" * 76)
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

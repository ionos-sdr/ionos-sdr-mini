# -*- coding: utf-8 -*-
"""ionos-sdr-mini digital twin, layer 5: the 3D model layer.

Layers 1-3 read the netlist, layer 4 reads the board geometry.  This one
reads the 3D MODELS, because on 2026-10-05 they were the one artefact nothing
in the chain looked at - and they were wrong.

What went wrong, and why nothing caught it:

    The mezzanine terminals carried TFC-120-02-F-D-A.stp.  Our part is
    TFC-120-02-XX-D-A-K-TR: the -K is the polarising key, and the model does
    not have it.  On top of that the model sat at the plain default transform
    (rotate -90 0 0), which put its key at the pin-40 end while the WSTK
    socket keyway is at pin 1.  ERC and DRC never look at a 3D model; the
    alignment pins are symmetric about the centreline so a 180 deg spin does
    not move them; and the pads were right.  It took a human staring at the
    3D view.

So this layer asks two questions a machine can answer:

  A  text only, always runs
     Is the attached model the part we are actually buying?  Does its
     transform say anything, or is it the default nobody checked?

  B  machine vision, --render
     Render the board top down and measure where the asymmetric feature of
     each declared part actually ends up.  This measures what KiCad DRAWS,
     which is the final truth: it includes the offset, the rotation, the
     scale and whatever assembly transforms hide inside the STEP.

Usage:
    kicad-python twin_3d.py [board.kicad_pcb] [--render] [-q]
"""
import os, re, sys, math, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_3d as S

import pcbnew

PRJ = os.path.dirname(HERE)
DEFAULT_PCB = os.path.join(PRJ, "ionosSDR_mini.kicad_pcb")
OUTDIR = os.path.join(HERE, "mech")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
log = []
MM = pcbnew.ToMM


def say(level, group, msg):
    log.append((level, group, msg))


# --------------------------------------------------------------- helpers ---
def kicad_path_vars():
    """KiCad's own path variables, from kicad_common.json and the environment.

    Without these, every model under ${RPW_LIB} looks missing and the layer
    reports forty false failures - which is worse than not checking at all.
    """
    import json, glob
    out = dict(os.environ)
    roots = []
    if os.name == "nt":
        roots.append(os.path.join(os.environ.get("APPDATA", ""), "kicad"))
    roots.append(os.path.expanduser("~/.config/kicad"))
    roots.append(os.path.expanduser("~/Library/Preferences/kicad"))
    for root in roots:
        for cfg in sorted(glob.glob(os.path.join(root, "*", "kicad_common.json"))):
            try:
                with open(cfg, encoding="utf-8") as fh:
                    env = (json.load(fh).get("environment") or {}).get("vars") or {}
                out.update({k: str(v) for k, v in env.items()})
            except (OSError, ValueError):
                pass
    return out


_VARS = None


def expand(path, pcb_path):
    """Resolve KiCad's path variables well enough to find the file."""
    global _VARS
    if _VARS is None:
        _VARS = kicad_path_vars()
    out = path.replace("\\", "/")
    out = out.replace("${KIPRJMOD}", os.path.dirname(pcb_path))
    out = out.replace("$(KIPRJMOD)", os.path.dirname(pcb_path))
    for name, value in _VARS.items():
        out = out.replace("${%s}" % name, value).replace("$(%s)" % name, value)
    return os.path.normpath(out.replace("\\", "/"))


def tokens(name):
    """Part-number tokens, upper case, no extension or library prefix."""
    name = os.path.splitext(os.path.basename(name))[0]
    name = name.split(":")[-1]
    return [t for t in re.split(r"[-_. ]+", name.upper()) if t]


def step_facts(path):
    """What can be learned from a STEP without a geometry kernel."""
    try:
        raw = open(path, "r", errors="ignore").read()
    except OSError as e:
        return {"error": str(e)}
    flat = re.sub(r"\s+", "", raw)
    f = {"kB": len(raw) // 1024,
         "assembly": flat.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE"),
         "transforms": flat.count("ITEM_DEFINED_TRANSFORMATION"),
         "points": flat.count("CARTESIAN_POINT"),
         "faces": flat.count("ADVANCED_FACE"),
         "inch": "CONVERSION_BASED_UNIT('INCH'" in flat}
    if f["assembly"] == 0 and f["transforms"] == 0:
        pts = re.findall(
            r"CARTESIAN_POINT\('[^']*',\(([-0-9.Ee+]+),([-0-9.Ee+]+),([-0-9.Ee+]+)\)\)", flat)
        if pts:
            xs = [float(a) for a, b, c in pts]
            ys = [float(b) for a, b, c in pts]
            zs = [float(c) for a, b, c in pts]
            f["bbox"] = [(min(v), max(v)) for v in (xs, ys, zs)]
    return f


# ------------------------------------------------------------- tier A ------
def check_models(board, pcb_path):
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    no_model = [r for r, fp in sorted(by_ref.items()) if len(list(fp.Models())) == 0]
    if no_model:
        say(WARN, "present", "%d footprints carry no 3D model at all: %s"
            % (len(no_model), ", ".join(no_model[:12]) + (" ..." if len(no_model) > 12 else "")))
    else:
        say(PASS, "present", "every footprint carries a 3D model")

    for ref, want in sorted(S.EXPECT.items()):
        fp = by_ref.get(ref)
        if fp is None:
            say(FAIL, "present", "%s is in the spec but not on the board" % ref)
            continue
        models = list(fp.Models())
        if not models:
            lvl = FAIL if want["must_have_model"] else WARN
            say(lvl, "present", "%s (%s) has no 3D model" % (ref, want["part"]))
            continue
        if len(models) > 1:
            say(WARN, "present", "%s carries %d models; only the first is checked"
                % (ref, len(models)))
        say(PASS, "present", "%s has a model (%s)"
            % (ref, os.path.basename(models[0].m_Filename)))

    # ---- the check that would have caught it: variant match ---------------
    for ref, want in sorted(S.EXPECT.items()):
        fp = by_ref.get(ref)
        if fp is None or not list(fp.Models()):
            continue
        m = list(fp.Models())[0]
        want_tok = set(tokens(want["part"]))
        have_tok = set(tokens(m.m_Filename))
        missing = sorted((want_tok - have_tok) & set(S.SHAPE_TOKENS))
        extra = sorted((have_tok - want_tok) & set(S.SHAPE_TOKENS))
        if missing or extra:
            say(FAIL, "variant",
                "%s: model '%s' is not the part we buy (%s). Shape tokens missing: %s%s"
                % (ref, os.path.basename(m.m_Filename), want["part"],
                   ", ".join(missing) or "none",
                   "; unexpected: " + ", ".join(extra) if extra else ""))
        else:
            say(PASS, "variant", "%s: model matches %s on every shape token"
                % (ref, want["part"]))

    # ---- the file is actually there ---------------------------------------
    for ref, fp in sorted(by_ref.items()):
        for m in fp.Models():
            p = expand(m.m_Filename, pcb_path)
            if not os.path.exists(p):
                say(FAIL, "resolve", "%s: model file not found: %s" % (ref, m.m_Filename))
            elif ref in S.EXPECT:
                f = step_facts(p)
                if "error" in f:
                    say(WARN, "resolve", "%s: cannot read %s (%s)" % (ref, p, f["error"]))
                    continue
                say(PASS, "resolve",
                    "%s: %s, %d kB, %d faces%s"
                    % (ref, os.path.basename(p), f["kB"], f["faces"],
                       ", assembly with %d transforms" % f["transforms"] if f["assembly"] else ""))
                if f["assembly"]:
                    say(WARN, "resolve",
                        "%s: the STEP is an assembly, so its envelope cannot be measured "
                        "from the file without a geometry kernel - use --render" % ref)

    # ---- transform sanity --------------------------------------------------
    for ref, fp in sorted(by_ref.items()):
        for m in fp.Models():
            sc = (m.m_Scale.x, m.m_Scale.y, m.m_Scale.z)
            if tuple(round(v, 6) for v in sc) != S.ALLOWED_SCALE:
                say(FAIL, "transform", "%s: model scale is %s, expected %s"
                    % (ref, sc, S.ALLOWED_SCALE))
            off = (m.m_Offset.x, m.m_Offset.y, m.m_Offset.z)
            allowed = S.OFFSET_EXCEPTIONS.get(ref)
            if allowed is None and max(abs(v) for v in off) > S.ALLOWED_OFFSET_MM:
                say(WARN, "transform", "%s: model offset is %s mm and nothing declares why"
                    % (ref, tuple(round(v, 3) for v in off)))
            rot = tuple(round(v, 3) for v in (m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z))
            if any(abs(v % S.ROTATION_STEP_DEG) > 1e-6 for v in rot):
                say(WARN, "transform", "%s: model rotation %s is not a multiple of %g deg"
                    % (ref, rot, S.ROTATION_STEP_DEG))
            want = S.VERIFIED_ROTATION.get(ref)
            if want is not None:
                same = all(abs((a - bq) % 360.0) < 1e-6 for a, bq in zip(rot, want))
                if same:
                    say(PASS, "transform", "%s: rotation %s, as verified" % (ref, rot))
                else:
                    say(FAIL, "transform",
                        "%s: rotation is %s but %s was verified by render on 2026-10-05; "
                        "if this is deliberate, re-verify and update spec_3d"
                        % (ref, rot, want))


# ------------------------------------------------------------- tier B ------
def render_part(pcb_path, board, ref, png, zoom, width, height):
    """Render one part, centred, at a repeatable zoom and pivot."""
    cli = os.environ.get("KICAD_CLI")
    if not cli:
        for cand in (r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
                     "/usr/bin/kicad-cli", "kicad-cli"):
            if os.path.exists(cand) or cand == "kicad-cli":
                cli = cand
                break
    bb = board.GetBoardEdgesBoundingBox()
    cx, cy = MM(bb.GetCenter().x), MM(bb.GetCenter().y)
    fp = {f.GetReference(): f for f in board.GetFootprints()}[ref]
    p = fp.GetPosition()
    pivot = "%.2f,%.2f,0" % ((MM(p.x) - cx) / 10.0, -(MM(p.y) - cy) / 10.0)
    subprocess.run([cli, "pcb", "render", pcb_path, "-o", png, "--side", "top",
                    "--zoom", str(zoom), "--pivot", pivot,
                    "--width", str(width), "--height", str(height),
                    "--quality", "high", "--background", "opaque"],
                   check=True, capture_output=True)
    return png


def check_orientation(board, pcb_path):
    """Has the 3D appearance of a polarised part changed since it was verified?

    WHAT THIS IS, HONESTLY: a regression test, not an absolute judgement.  No
    machine here can tell you which end of a shrouded connector ought to carry
    the key - that came from the physical WSTK on the bench.  What a machine
    CAN do is hold the line afterwards, so a later edit cannot silently spin
    the model back.

    Two weaker designs were tried and thrown away, both because they were
    measured rather than assumed:

      * "which end of the part is brighter" - the render's lighting gradient
        swamps the key, and the statistic moved by 0.45 out of 4.8 between the
        correct and the 180 deg-wrong model.  Inside the noise.
      * the same statistic on a full-board render - at 5 px/mm the 2 mm key
        block is ten pixels wide and simply is not there.

    The reference-image comparison was calibrated on the same two cases:
        render noise, same scene twice   mean|d| 0.23, 0.05 %% of pixels over 25
        model spun 180 deg               mean|d| 0.64, 0.40 %% of pixels over 25
    an eight-fold separation on the pixel fraction, so the gate sits between.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        say(WARN, "orient", "Pillow and numpy are needed for the render check")
        return

    os.makedirs(OUTDIR, exist_ok=True)
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref in sorted(S.ASYM_END):
        if ref not in by_ref:
            continue
        cur = os.path.join(OUTDIR, "orient_%s.png" % ref)
        refimg = os.path.join(HERE, "ref3d", "%s.png" % ref)
        try:
            render_part(pcb_path, board, ref, cur,
                        S.RENDER["zoom"], S.RENDER["width"], S.RENDER["height"])
        except Exception as e:
            say(WARN, "orient", "%s: kicad-cli render failed: %s" % (ref, e))
            continue

        if not os.path.exists(refimg):
            os.makedirs(os.path.dirname(refimg), exist_ok=True)
            Image.open(cur).save(refimg)
            say(WARN, "orient",
                "%s: no reference image yet, so this render was stored as one. "
                "LOOK AT twin/ref3d/%s.png NOW and confirm the key is at the %s "
                "end, then commit it - everything after this only checks that "
                "nothing moved." % (ref, ref, S.ASYM_END[ref]))
            continue

        a = np.asarray(Image.open(refimg).convert("L")).astype(float)
        b = np.asarray(Image.open(cur).convert("L")).astype(float)
        if a.shape != b.shape:
            say(WARN, "orient", "%s: reference is %s, this render is %s - "
                "re-capture the reference" % (ref, a.shape, b.shape))
            continue
        d = abs(a - b)
        frac = float((d > S.PIXEL_DELTA).mean())
        if frac > S.PIXEL_FRACTION_MAX:
            say(FAIL, "orient",
                "%s: the 3D appearance changed - %.2f%% of pixels differ by more "
                "than %d levels, against %.2f%% for render noise and %.2f%% for a "
                "180 deg spin. Open twin/mech/orient_%s.png beside "
                "twin/ref3d/%s.png and see what moved."
                % (ref, 100 * frac, S.PIXEL_DELTA, 100 * S.NOISE_FRACTION,
                   100 * S.FLIP_FRACTION, ref, ref))
        else:
            say(PASS, "orient",
                "%s: unchanged against the verified reference (%.3f%% of pixels "
                "differ, noise floor %.3f%%)"
                % (ref, 100 * frac, 100 * S.NOISE_FRACTION))


def selftest(pcb_path):
    """Spin a model 180 deg on a scratch copy and demand that we catch it.

    Same rule as twin_plug: a verifier nobody has watched fail is not a
    verifier.  This one has to exist because two earlier designs of this check
    passed happily on a board that was wrong.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("selftest needs Pillow and numpy")
        return 3

    board = pcbnew.LoadBoard(pcb_path)
    # the scratch board must sit in the project folder or ${KIPRJMOD} breaks
    # and NOTHING renders - which looks exactly like a passing test.
    work = os.path.join(os.path.dirname(pcb_path), "_twin3d_selftest.kicad_pcb")
    src = open(pcb_path, encoding="utf-8").read()
    pat = re.compile(r"(\(rotate\s*\(xyz\s*)-90 0 180(\s*\))")
    out, n = pat.subn(lambda m: m.group(1) + "-90 0 0" + m.group(2), src)
    if n == 0:
        print("selftest: nothing to spin; are the models still at -90 0 180?")
        return 3
    open(work, "w", encoding="utf-8").write(out)
    print("selftest: spun %d model(s) by 180 deg on a scratch copy" % n)

    caught = 0
    try:
        wb = pcbnew.LoadBoard(work)
        for ref in sorted(S.ASYM_END):
            refimg = os.path.join(HERE, "ref3d", "%s.png" % ref)
            if not os.path.exists(refimg):
                print("  %s: no reference image, cannot self-test" % ref)
                continue
            png = os.path.join(OUTDIR, "selftest_%s.png" % ref)
            render_part(work, wb, ref, png,
                        S.RENDER["zoom"], S.RENDER["width"], S.RENDER["height"])
            a = np.asarray(Image.open(refimg).convert("L")).astype(float)
            b = np.asarray(Image.open(png).convert("L")).astype(float)
            frac = float((abs(a - b) > S.PIXEL_DELTA).mean())
            ok = frac > S.PIXEL_FRACTION_MAX
            print("  %s: %.3f%% of pixels differ, gate %.3f%% -> %s"
                  % (ref, 100 * frac, 100 * S.PIXEL_FRACTION_MAX,
                     "CAUGHT" if ok else "MISSED"))
            caught += 1 if ok else 0
    finally:
        for ext in (".kicad_pcb", ".kicad_prl"):
            p = os.path.splitext(work)[0] + ext
            if os.path.exists(p):
                os.remove(p)

    want = len([r for r in S.ASYM_END
                if os.path.exists(os.path.join(HERE, "ref3d", "%s.png" % r))])
    print("selftest: caught %d of %d" % (caught, want))
    return 0 if caught == want and want else 3


# ----------------------------------------------------------------- main ----
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    pcb_path = args[0] if args else DEFAULT_PCB
    if not os.path.exists(pcb_path):
        print("no board at", pcb_path)
        return 2
    if "--selftest" in sys.argv:
        return selftest(pcb_path)
    board = pcbnew.LoadBoard(pcb_path)

    check_models(board, pcb_path)
    if "--render" in sys.argv:
        check_orientation(board, pcb_path)
    else:
        say(WARN, "orient",
            "the orientation check did not run; pass --render to compare what "
            "KiCad draws against the verified reference")

    groups = {}
    for lvl, grp, msg in log:
        groups.setdefault(grp, []).append((lvl, msg))
    titles = [("present", "is there a model at all"),
              ("variant", "is it the part we are buying"),
              ("resolve", "does the file exist, and what is in it"),
              ("transform", "offset, scale and rotation"),
              ("orient", "has the 3D appearance changed since it was verified")]
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
    npass = sum(1 for l, g, m in log if l == PASS)
    print("\n" + "=" * 76)
    print(" RESULT: %d pass, %d warn, %d FAIL" % (npass, nw, nf))
    print("=" * 76)
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Specification for the 3D layer of the digital twin.

Same discipline as every other spec_*.py in this folder: NOTHING here may be
read out of our own board.  Every line names the document or the physical
part it came from.  If you write this file from the .kicad_pcb you are only
proving the board agrees with itself.

WHY THIS LAYER EXISTS
---------------------
2026-10-05.  The mezzanine terminals carried the STEP file
``TFC-120-02-F-D-A.stp`` with the plain default transform
``(rotate (xyz -90 -0 -0))``.  Two things were wrong and nothing caught them:

  1. the model is a DIFFERENT VARIANT from the part we buy -- our footprint is
     ``TFC-120-02-XX-D-A-K-TR`` (``-K`` = keyed), the model has no ``-K``;
  2. the body was 180 deg out about Z, so its polarising key sat at the pin-40
     end while the WSTK socket keyway is at pin 1.

Pads and alignment holes were never affected, which is exactly why it stayed
invisible: the alignment pins are symmetric about the centreline (+-13.655 mm),
so a 180 deg spin does not move them, and KiCad's ERC and DRC never look at a
3D model at all.  It only showed up when a human looked at the 3D view.

So this layer asks the two questions that would have caught it on day one:
is the model the part we are actually buying, and does its asymmetric feature
point the way the mating part demands.
"""

# --------------------------------------------------------------------------
# 1.  Which reference gets which model, and what the part number really is.
#     Source: our own BOM / Samtec part numbering, not the board file.
# --------------------------------------------------------------------------
# Samtec naming:  TFC = Terminal (male), SFC = Socket (female).
#   -A  alignment pins        -K  keyed (polarising block in the shroud)
#   -TR tape and reel         the  -XX-  field is the plating code
EXPECT = {
    "CON1": {"part": "TFC-120-02-XX-D-A-K-TR",
             "must_have_model": True,
             "source": "BOM; Samtec TFC series drawing"},
    "CON2": {"part": "TFC-120-02-XX-D-A-K-TR",
             "must_have_model": True,
             "source": "BOM; Samtec TFC series drawing"},
    "IC1":  {"part": "ESP32-S3-DEVKITC-1",
             "must_have_model": True,
             "source": "Espressif ESP32-S3-DevKitC-1 v1.1 mechanical drawing"},
    "DISP1": {"part": "SSD1306-OLED-128x64",
              "must_have_model": True,
              "source": "module datasheet"},
}

# Tokens in a part number that change the SHAPE of the part.  A model whose
# name is missing one of these is not the part we are buying, however close
# the rest of the string looks.  This is the check that catches -F- vs -K.
#   -TR and -LF are packaging and plating, they do not change the shape, so
#   they are deliberately NOT in this list - a verifier that flags harmless
#   differences teaches people to ignore it.
SHAPE_TOKENS = ("A", "K", "D", "S")

# --------------------------------------------------------------------------
# 2.  Declared orientation of the asymmetric feature.
#     Source: the PHYSICAL Silabs WSTK on the bench, both horizontal sockets,
#     2026-10-05: the keyway (bemaras) in the socket is at the pin-1 end,
#     bottom-left.  Cross-checked against the Samtec SFC-120-T2-L-D-A decal in
#     Silabs' own WSTK adapter source, WES0108-03_ASCII.asc.
#     A key and its keyway must sit at the SAME end of a mated pair, so our
#     male terminal carries its key at pin 1 too.
# --------------------------------------------------------------------------
ASYM_END = {
    "CON1": "pin1",
    "CON2": "pin1",
}

# The orientation check is a REGRESSION test against a human-verified render,
# not an absolute judgement - see the long note in twin_3d.check_orientation.
# These numbers are measurements, not guesses.
#
# Only the part's own courtyard (+ROI_MARGIN_MM) is compared, not the whole
# frame: in rev-B2 the D-pad moved 3 mm and SW1 entered CON2's render frame,
# which a whole-frame compare would have reported as a changed connector.
#
# Calibrated 2026-10-08 on CON1/CON2, rendered with the verified rotation and
# with the default that was wrong, ROI only:
#
#     same scene rendered twice   0.04 % of ROI pixels differ by over 40 levels
#     model spun 180 deg about Z  1.35 %
#
# 34x separation; the gate sits at 0.30 %.  (At 25 levels it was 0.24 % vs
# 1.81 %, only 7.5x - hence 40.)
#
# RENDER_PX_PER_MM was measured from the 1.27 mm pin pitch by autocorrelation,
# 20.13 px/mm on three renders.  It depends on the board outline (the render
# fits the board to the frame) - re-measure if the outline changes.
RENDER = {"zoom": 5, "width": 1000, "height": 700}
RENDER_PX_PER_MM = 20.13
ROI_MARGIN_MM = 1.0
PIXEL_DELTA = 40             # a pixel "differs" past this many grey levels
NOISE_FRACTION = 0.0004      # measured render-to-render noise, ROI
FLIP_FRACTION = 0.0135       # measured for a 180 deg spin, ROI
PIXEL_FRACTION_MAX = 0.0030  # fail above this

# --------------------------------------------------------------------------
# 3.  Transform sanity.  Anything outside this is an import accident until
#     somebody writes down why.
# --------------------------------------------------------------------------
ALLOWED_SCALE = (1.0, 1.0, 1.0)
ALLOWED_OFFSET_MM = 0.001          # must be zero unless declared below
OFFSET_EXCEPTIONS = {              # ref -> (x, y, z) that is known-good
    # buydisplay ER-TFTM024-3.STEP (SolidWorks 2023, 2024-06-07), measured with an OCC kernel:
    # its four 2.8 mm mounting holes at X -28.79 / 23.21, Y 23.45 / -35.05 (52.0 x 58.5 mm)
    # land on the footprint holes (-1.87, 8.74) ... (50.13, 67.24) rel. pin 1 with X +26.92,
    # Y -32.19; module PCB bottom (z -0.81) on an 8.5 mm female socket -> Z +9.31.
    # NOTE the STEP draws a 2x21 header (42 pins, half a pitch off our 2x20 grid); the
    # datasheet and the footprint say 2x20 - holes and outline match exactly, so the
    # placement is right and the pin row is the vendor model's error.
    # PHYSICAL CHECK 2026-10-08 (photos of the drawer panel, Ver 2.0): male 2x20 header on
    # the back, silk "1"/"2" at one end and "39"/"40" at the other, pin 2 on the row away
    # from the edge - seen from the top that is pin 1 left, pin 2 inward, as the footprint.
    "DISP2": (26.92, -32.19, 9.31),
}
ROTATION_STEP_DEG = 90.0           # rotations must be multiples of this

# Declared transforms we have verified by eye in the 3D view and by render
# measurement.  A change away from these should be noticed.
VERIFIED_ROTATION = {
    "CON1": (-90.0, 0.0, 180.0),   # verified 2026-10-05 by top render
    "CON2": (-90.0, 0.0, 180.0),
}

# --------------------------------------------------------------------------
# 4.  Heights, for cross-checking spec_mech's hand-typed numbers.
#     Source: Samtec TFC-120-02 lead style -02 -> 6.35 mm mated height.
# --------------------------------------------------------------------------
DECLARED_HEIGHT_MM = {
    "CON1": 6.35,
    "CON2": 6.35,
}

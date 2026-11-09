# -*- coding: utf-8 -*-
"""Mechanical specification of everything that plugs into the carrier.

Layer 4 of the twin.  Layers 1-3 reason about nets; this one reasons about
millimetres - and it is the layer that catches the mistake no netlist check
can see: a connector footprint placed the wrong way round.  The pads still
line up perfectly, only the pin NUMBERS are reversed, so nothing in the
schematic, the ERC, the DRC or the netlist twin can notice.

Everything below was read out of the manufacturer's own files.

SOURCES
  [G-DRL]  PCB4265B_A01.DRL / .DRR  - drill file and report
  [G-GM1]  PCB4265B_A01.GM1         - board outline
  [G-GBL]  PCB4265B_A01.GBL         - bottom copper (connector pads)
  [G-GBO]  PCB4265B_A01.GBO         - bottom silkscreen (P200/P201, pin 40)
  [ASSY]   PCB4265B-A01-assy-draw.pdf, sheet 2 "Bottom Assembly"
  [SAMTEC] TFC-120-02-X-D-A-K datasheet, lead style -02
  [ESP]    rpw_lib XCVR_ESP32-S3-DEVKITC-1 footprint outline;
           Espressif's own DXF has NOT been checked - see DEVKIT_UNVERIFIED
"""

# =====================================================================
#  BRD4265B radio board - top-view local coordinates, origin bottom-left
# =====================================================================
RB = {
    "name": "BRD4265B-A01",
    "outline_mm": (30.000, 45.000),          # [G-GM1]
    "corner_radius_mm": 1.200,               # [G-GM1]
    "thickness_mm": 1.0,                     # [ASSY] nominal radio-board stack
}

# 4 x NPTH, the alignment pins of the two mezzanine connectors   [G-DRL]
RB_ALIGN_D = 1.349
RB_ALIGN = [(1.349, 5.001), (28.651, 5.001),
            (1.349, 28.999), (28.651, 28.999)]

# The two sockets.  centre_v is the connector centreline; pin 1 sits at the
# LOW-u end and in the row 1.45 mm BELOW the centreline.  Both facts are
# read from [G-GBO] (the "40" legend is at the high-u end on both) and
# confirmed against [G-GBL]: the 40-pad copper pattern of P201 matches its
# known connectivity bit for bit in this orientation and in no other.
RB_SOCKETS = {
    "P200": {"centre_v": 29.000, "pin1_u": 2.935, "odd_row_dv": -1.45},
    "P201": {"centre_v": 5.000,  "pin1_u": 2.935, "odd_row_dv": -1.45},
}
RB_PITCH = 1.270
RB_COLS = 20
RB_PAD = (0.74, 2.00)                        # [G-GBL] 29.13 x 78.74 mil

# SMA: centre pin + 4 ground posts on a 5.08 mm square   [G-DRL]
RB_SMA = {"centre": (25.601, 38.600), "pin_d": 1.501,
          "post_d": 1.600, "post_pitch": 5.080}

# What stands on the radio board's UNDERSIDE, i.e. facing our carrier.
# From [ASSY] sheet 2: the two sockets, U200 (M24C02, SOIC-8), RP200, 20
# test pads and a handful of 0402/0805.  Nothing tall.
RB_BOTTOM_MAX_H = 1.10                       # SOIC-8 body, worst case


def rb_pin(socket, n):
    """(u, v) of pin n of a radio-board socket, top-view local coords."""
    s = RB_SOCKETS[socket]
    col = (n - 1) // 2
    dv = s["odd_row_dv"] if n % 2 else -s["odd_row_dv"]
    return (s["pin1_u"] + col * RB_PITCH, s["centre_v"] + dv)


# Which of our connectors mates with which socket, and the resulting
# transform.  The radio board is flipped about its u axis, so
#     X = u + Tx,   Y = Ty - v
# and Ty is fixed by the requirement that P200 meets CON1.  There is no
# other axis-aligned placement that puts the two sockets 24 mm apart in the
# right order, so this transform is unique.
MATES = {"CON1": "P200", "CON2": "P201"}

# =====================================================================
#  Samtec TFC-120-02-X-D-A-K terminal on our side
# =====================================================================
SAMTEC = {
    "pitch_mm": 1.270,
    "cols": 20,
    "row_spacing_mm": 3.430,      # pad centres; the socket's are 2.90 apart
    "align_spacing_mm": 27.310,
    "align_hole_d_mm": 1.420,
    "mated_height_mm": 6.35,      # [SAMTEC] lead style -02
}

# Height left under the radio board once it is seated.
UNDER_RADIO_MM = SAMTEC["mated_height_mm"] - RB_BOTTOM_MAX_H      # 5.25 mm

# =====================================================================
#  ESP32-S3-DevKitC-1
# =====================================================================
DEVKIT = {
    "header": {"rows": 2, "pins_per_row": 22, "pitch_mm": 2.54,
               "row_spacing_mm": 22.86},
    # from the rpw_lib footprint's F.Fab outline, relative to the origin
    "outline_rel": (-13.72, -31.37, 12.70, 31.37),
    "outline_mm": (26.42, 62.74),
}
# Third-party sources quote 70 x 28 mm for this board, the footprint says
# 26.42 x 62.74.  Espressif's own drawing (DXF_ESP32-S3-DevKitC-1_V1.1)
# has NOT been checked, so the module envelope is an UNVERIFIED input and
# the checker says so rather than passing it silently.
DEVKIT_UNVERIFIED = ("module envelope: footprint says %.2f x %.2f mm, "
                     "third-party sources say 70 x 28 mm - confirm against "
                     "Espressif DXF_ESP32-S3-DevKitC-1_V1.1_20220429"
                     % DEVKIT["outline_mm"])
# The module sits on a 2.54 mm header; nothing of ours may be taller than
# this underneath it.  Soldered flat, it would be zero.
UNDER_DEVKIT_MM = 8.50

# =====================================================================
#  component heights, for the clearance checks
# =====================================================================
HEIGHTS = {
    "0402": 0.55, "0603": 0.95, "0805": 1.10, "1206": 1.15,
    "SOT-23": 1.30, "SOT-353": 1.10, "SOT-563": 0.60,
    "L5_0603": 1.00, "TESTPOINT": 0.10, "SolderJumper": 0.05,
}


def height_of(lib_id, value=""):
    """Best guess at a part's height from its footprint name."""
    s = (lib_id or "").upper()
    for key, h in HEIGHTS.items():
        if key.upper() in s:
            return h
    if "0402" in s or "1005" in s:
        return 0.55
    if "0603" in s or "1608" in s:
        return 0.95
    if "0805" in s or "2012" in s:
        return 1.10
    if "SOT" in s:
        return 1.30
    if "MOUNT" in s or "HOLE" in s:
        return 0.0
    return None          # unknown - the checker reports it rather than guess


# Footprints that are allowed to have no courtyard (none, really - this is
# here so the rule is explicit rather than implied).
COURTYARD_EXEMPT = set()

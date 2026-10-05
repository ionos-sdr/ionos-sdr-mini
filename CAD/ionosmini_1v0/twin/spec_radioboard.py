# -*- coding: utf-8 -*-
"""What is on the other side of the socket: the Silabs BRD4265B radio board.

This file is the "mama" in the cradle.  It describes, pin by pin, what the
radio board connects to each of the 80 mezzanine pins, so the twin can plug
the board in on paper and follow every signal from the ESP32 all the way to
an EFR32FG23 port pin - and, just as important, notice when a carrier signal
lands somewhere it should not.

SOURCES (all read directly, nothing assumed):

  [S4]  BRD4265B-A01 schematic, page 4 "WSTK Connectors"
        P200 and P201 symbols, pin by pin.
  [S3]  BRD4265B-A01 schematic, page 3 "Pin Mapping / I/O Port Pins"
        The EFR32 <-> WSTK_P <-> WSTK_F wiring, and the U1A symbol
        (EFR32FG23B010F512IM48, QFN48) with its package pin numbers.
  [S2]  BRD4265B-A01 schematic, page 2 "Radio Interface"
        EFR32_RESET -> U1 pin 13, no external pull-up on the radio board.
  [BOM] BRD4265B-A01 BOM: R201 0R fitted, R216 0R fitted, R217 0R NM,
        R210 NM, RP200 100R array, P200/P201 = WCON 2344-220MS3CUNR6.
  [PCB] PCB4265B_A01.PcbDoc net list (77 nets), used only to cross-check
        the merged-net names derived from [S3].  Every conclusion below is
        independently readable on the schematic.

A NOTE ON THE TRACE PINS.  On page 3 five EFR32 port pins are tapped a
second time onto the WSTK_P41..P45 breakout pins for ETM trace.  Those taps
were read off the schematic geometrically (junction-dot positions), then
confirmed against the PcbDoc net names: PA06's merged net really is called
WSTK_P44, PA05's is WSTK_P4, PA07's is WSTK_P10 - exactly what the taps
predict.  They matter because they put three of OUR signals (FG23_CS,
FG23_CMD, FG23_SPARE) on a second socket pin as well.
"""

BOARD = "BRD4265B-A01"
MCU = "EFR32FG23B010F512IM48"      # U1A on [S3], QFN48
MCU_REF = "U1"

# The carrier's reference designators for the two mezzanine sockets.
CON_OF = {"P200": "CON1", "P201": "CON2"}
SOCKET_OF = dict((v, k) for k, v in CON_OF.items())

# --------------------------------------------------------------- [S4]
# Fixed (non-breakout) pins of the two connectors, read off the symbols.
FIXED = {
    ("P200", 1):  "3V3",            # supply INTO the radio board
    ("P200", 2):  "GND",
    ("P200", 35): "5V",             # supply INTO the radio board
    ("P200", 36): "USB_VREG",
    ("P200", 37): "USB_VBUS",
    ("P200", 38): "GND",
    ("P200", 39): "BOARD_ID_SCL",
    ("P200", 40): "BOARD_ID_SDA",
    ("P201", 1):  "GND",
    ("P201", 2):  "VMCU_IN",        # supply INTO the radio board, via R201 0R
    ("P201", 39): "GND",
    ("P201", 40): "NC",             # drawn with an X on [S4]
}


def _breakout():
    """The breakout pins of the two connectors, exactly as drawn on [S4]."""
    m = {}
    for p in range(3, 13):          # P200 3..12  -> WSTK_P36..P45
        m[("P200", p)] = "WSTK_P%d" % (p + 33)
    for p in range(13, 35):         # P200 13..34 -> WSTK_F0..F21
        m[("P200", p)] = "WSTK_F%d" % (p - 13)
    for p in range(3, 39):          # P201 3..38  -> WSTK_P0..P35
        m[("P201", p)] = "WSTK_P%d" % (p - 3)
    return m


MEZZ = dict(FIXED)
MEZZ.update(_breakout())

# --------------------------------------------------------------- [S3]
# WSTK breakout net -> the node it reaches on the radio board.
# Each entry: (node, series element, note)
#   node    - the electrical node on the radio board.  "PAnn"/"PBnn"/... is
#             an EFR32 port pin, everything else is named after its function.
#   series  - None for a direct wire, otherwise (ref, ohms, fitted)
#   note    - the WSTK function the pin has on a real starter kit
WSTK = {
    # ---- debug / trace, each on two breakout pins -------------------
    "WSTK_P20": ("PA01", None, "DBG_TCK_SWCLK"),
    "WSTK_F1":  ("PA01", None, "DBG_TCK_SWCLK (second route)"),
    "WSTK_P18": ("PA02", None, "DBG_TMS_SWDIO"),
    "WSTK_F0":  ("PA02", None, "DBG_TMS_SWDIO (second route)"),
    "WSTK_P16": ("PA03", None, "DBG_TDO_SWO"),
    "WSTK_F2":  ("PA03", None, "DBG_TDO_SWO (second route)"),
    "WSTK_P42": ("PA03", None, "DEBUG_TRACED0 tap (third route)"),
    "WSTK_P14": ("PA04", None, "DBG_TDI"),
    "WSTK_F3":  ("PA04", None, "DBG_TDI (second route)"),
    "WSTK_P41": ("PA04", None, "DEBUG_TRACECLK tap (third route)"),
    # ---- the EXP-header port pins -----------------------------------
    "WSTK_P4":  ("PA05", None, "EXP_HEADER7"),
    "WSTK_P43": ("PA05", None, "DEBUG_TRACED1 tap (second route)"),
    "WSTK_P8":  ("PA06", None, "EXP_HEADER11"),
    "WSTK_P44": ("PA06", None, "DEBUG_TRACED2 tap (second route)"),
    "WSTK_P10": ("PA07", None, "EXP_HEADER13"),
    "WSTK_P45": ("PA07", None, "DEBUG_TRACED3 tap (second route)"),
    # ---- VCOM ------------------------------------------------------
    "WSTK_P2":  ("PA00", None, "VCOM_RTS"),
    "WSTK_F9":  ("PA00", None, "VCOM_RTS (second route)"),
    "WSTK_P9":  ("PA08", None, "VCOM_TX"),
    "WSTK_F6":  ("PA08", None, "VCOM_TX (second route)"),
    "WSTK_P11": ("PA09", None, "VCOM_RX"),
    "WSTK_F7":  ("PA09", None, "VCOM_RX (second route)"),
    "WSTK_P0":  ("PA10", None, "VCOM_CTS"),
    "WSTK_F8":  ("PA10", None, "VCOM_CTS (second route)"),
    "WSTK_P15": ("PB00", None, "VCOM_ENABLE"),
    "WSTK_F5":  ("PB00", None, "VCOM_ENABLE (second route)"),
    # ---- user interface --------------------------------------------
    "WSTK_P17": ("PB01", None, "UIF_BUTTON0"),
    "WSTK_F12": ("PB01", None, "UIF_BUTTON0 (second route)"),
    "WSTK_P19": ("PB02", None, "UIF_LED0"),
    "WSTK_F10": ("PB02", None, "UIF_LED0 (second route)"),
    "WSTK_P21": ("PB03", None, "UIF_BUTTON1"),
    "WSTK_F13": ("PB03", None, "UIF_BUTTON1 (second route)"),
    "WSTK_P26": ("PD03", None, "UIF_LED1"),
    "WSTK_F11": ("PD03", None, "UIF_LED1 (second route)"),
    # ---- USART1 / memory LCD, 100R series array RP200 ---------------
    "WSTK_P1":  ("PC01", ("RP200", 100.0, True), "US1_TX / DISP_SI"),
    "WSTK_F16": ("PC01", ("RP200", 100.0, True), "DISP_SI (second route)"),
    "WSTK_P3":  ("PC02", ("RP200", 100.0, True), "US1_RX"),
    "WSTK_P5":  ("PC03", ("RP200", 100.0, True), "US1_CLK / DISP_SCLK"),
    "WSTK_F15": ("PC03", ("RP200", 100.0, True), "DISP_SCLK (second route)"),
    "WSTK_P31": ("PC08", None, "DISP_SCS"),
    "WSTK_F17": ("PC08", None, "DISP_SCS (second route)"),
    "WSTK_P33": ("PC06", None, "DISP_EXTCOMIN"),
    "WSTK_F18": ("PC06", None, "DISP_EXTCOMIN (second route)"),
    "WSTK_P37": ("PC09", None, "SENSOR_ENABLE / DISP_ENABLE"),
    "WSTK_F14": ("PC09", None, "DISP_ENABLE (second route)"),
    # ---- the pins the ionos-sdr-mini actually uses ------------------
    "WSTK_P7":  ("PC00", None, "US1_CS / EXP_HEADER10"),
    "WSTK_P12": ("PC05", None, "I2C0_SCL / EXP_HEADER15"),
    "WSTK_P13": ("PC07", None, "I2C0_SDA / EXP_HEADER16"),
    "WSTK_P6":  ("PD02", ("R216", 0.0, True), "EXP_HEADER9, via R216 0R"),
    "WSTK_P36": ("PD02", ("R217", 0.0, False), "JOYSTICK, R217 is NOT mounted"),
    # ---- PTI --------------------------------------------------------
    "WSTK_P24": ("PD05", None, "PTI_SYNC"),
    "WSTK_F19": ("PD05", None, "PTI_SYNC (second route)"),
    "WSTK_P25": ("PD04", None, "PTI_DATA"),
    "WSTK_F20": ("PD04", None, "PTI_DATA (second route)"),
    # ---- reset ------------------------------------------------------
    "WSTK_F4":  ("RESETn", None, "DBG_RESET -> U1 pin 13 [S2]"),
    # ---- remaining port pin ----------------------------------------
    "WSTK_P35": ("PC04", None, "no WSTK function"),
}

# Breakout pins the radio board leaves open.  Derived, not guessed: every
# WSTK_P0..P45 / WSTK_F0..F21 name that does not appear in WSTK above.
OPEN = set()
for _i in range(46):
    if "WSTK_P%d" % _i not in WSTK:
        OPEN.add("WSTK_P%d" % _i)
for _i in range(22):
    if "WSTK_F%d" % _i not in WSTK:
        OPEN.add("WSTK_F%d" % _i)

# --------------------------------------------------------------- [S3]
# EFR32FG23B010F512IM48 port pin -> QFN48 package pin.
PKG = {
    "PA00": 25, "PA01": 26, "PA02": 27, "PA03": 28, "PA04": 29, "PA05": 30,
    "PA06": 31, "PA07": 32, "PA08": 33, "PA09": 34, "PA10": 35,
    "PB00": 24, "PB01": 23, "PB02": 22, "PB03": 21,
    "PC00": 1, "PC01": 2, "PC02": 3, "PC03": 4, "PC04": 5,
    "PC05": 6, "PC06": 7, "PC07": 8, "PC08": 9, "PC09": 10,
    "PD00": 48, "PD01": 47, "PD02": 46, "PD03": 45, "PD04": 44, "PD05": 43,
    "RESETn": 13,
}

# What kind of node each non-port name is, so the twin can judge whether a
# carrier signal may legally touch it.
KIND = {
    "GND": "gnd",
    "3V3": "supply_in",        # the carrier feeds it
    "5V": "supply_in",         # the carrier feeds it
    "VMCU_IN": "supply_in",    # the carrier feeds it, R201 0R -> VMCU
    "USB_VREG": "radio_out",   # driven by the radio board
    "USB_VBUS": "supply_in",
    # M24C02 EEPROM (U200).  NOTE: the only pull-up on the radio board is
    # R200 10K on BOARD_ID_WP - SDA and SCL have NO pull-up there, so the
    # bus pull-ups must come from the carrier (R6/R7, 4.7k).
    "BOARD_ID_SCL": "eeprom",
    "BOARD_ID_SDA": "eeprom",
    "RESETn": "mcu_reset",     # active low, internal pull-up only [S2]
    "NC": "nc",
}

IO_VOLTAGE = 3.3               # the FG23 runs off VMCU, which we feed with 3V3

# -------------------------------------------------------- what we expect
# The carrier net -> the EFR32 port pin it is meant to reach.  This is the
# designer's intent, stated once, in radio-board terms.  twin_plug.py proves
# the copper actually does it.
INTENT = {
    "FG23_SCLK":  "PC05",
    "FG23_MOSI":  "PC00",
    "FG23_CS":    "PA07",
    "FG23_CMD":   "PA06",
    "FG23_RDY":   "PD02",
    "FG23_SPARE": "PA05",
    "SWDIO":      "PA02",
    "SWCLK":      "PA01",
    "SWO":        "PA03",
    "RESETn":     "RESETn",
    "I2C_SCL":    "BOARD_ID_SCL",
    "I2C_SDA":    "BOARD_ID_SDA",
    "3V3_RADIO":  "3V3",
    "VMCU_IN":    "VMCU_IN",
}

# Who drives what, seen from the radio board.  Used for drive-conflict and
# direction checks.  "in" = the FG23 listens, "out" = the FG23 talks.
# The FG23 is the SPI MASTER of this link and the ESP32 is the slave, so
# SCLK/MOSI/CS are FG23 outputs.  RDY and CMD run the other way: the slave
# tells the master when its DMA is armed, and the host sends commands.
# Source: claude/FG23-SDRpp-fg23-scan-source-modul-2026-08-15.md (the
# EXP-header wiring table) and FG23-kijelzopanel-valasztas-2026-08-17.md.
RB_DIRECTION = {
    "PC05": "out",      # SCLK   - the FG23 clocks the link
    "PC00": "out",      # MOSI   - IQ / SPECLINE payload
    "PA07": "out",      # CS     - block framing
    "PA06": "in",       # CMD    - cmdlink from the host
    "PD02": "in",       # RDY    - handshake from the host
    "PA05": "bidir",    # spare
    "PA02": "bidir",    # SWDIO
    "PA01": "in",       # SWCLK
    "PA03": "out",      # SWO
    "RESETn": "in",
    "BOARD_ID_SCL": "in",
    "BOARD_ID_SDA": "bidir",
}


# ------------------------------------------------------------- helpers
def node_of(socket, pin):
    """What the radio board connects to (socket, pin).

    Returns (node, series, note).  node is None for a pin the radio board
    leaves open.
    """
    name = MEZZ.get((socket, pin))
    if name is None:
        return (None, None, "pin does not exist")
    if name in ("NC",):
        return (None, None, "marked NC on the Silabs sheet")
    if name.startswith("WSTK_"):
        if name in WSTK:
            return WSTK[name]
        return (None, None, "%s is not connected on this radio board" % name)
    return (name, None, "fixed mezzanine pin")


def pins_of_node(node):
    """Every (socket, pin) that reaches the given radio-board node."""
    out = []
    for (sock, pin) in sorted(MEZZ):
        n, series, note = node_of(sock, pin)
        if n == node:
            out.append((sock, pin, series, note))
    return out

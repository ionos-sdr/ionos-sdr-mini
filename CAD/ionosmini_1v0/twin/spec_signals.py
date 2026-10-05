# -*- coding: utf-8 -*-
"""Independent machine-readable specification of the ionos-sdr-mini wiring.

Written from the SOURCE DOCUMENTS, not from the schematic:

  * BRD4265B-A01 schematic, sheet 4 (P200 / P201 pin tables)
  * BRD4265B-A01 BOM and drill file (connector type and alignment pins)
  * ESP32-S3-WROOM-1 N16R8 datasheet (pin restrictions)
  * ER-TFTM024-3 datasheet section 4.1 (header pin assignment)

The checker compares the exported netlist against this.  If the two ever
disagree, one of them is wrong - and that is the whole point.
"""

# ---------------------------------------------------------------- mezzanine
# Verified on the Silabs sheet: P201 carries WSTK_P0..P35 on pins 3..38, so
# WSTK_Pn sits on P201 pin n+3.  P200 carries WSTK_F0..F21 on pins 13..34,
# so WSTK_Fn sits on P200 pin n+13.
def p201_pin(wstk_p):
    return wstk_p + 3


def p200_pin(wstk_f):
    return wstk_f + 13


CON_OF = {"P200": "CON1", "P201": "CON2"}

MEZZ_FIXED = {
    ("P200", 1): "3V3", ("P200", 2): "GND",
    ("P200", 35): "5V", ("P200", 36): "USB_VREG", ("P200", 37): "USB_VBUS",
    ("P200", 38): "GND",
    ("P200", 39): "BOARD_ID_SCL", ("P200", 40): "BOARD_ID_SDA",
    ("P201", 1): "GND", ("P201", 2): "VMCU_IN",
    ("P201", 39): "GND", ("P201", 40): "NC",
}

# ------------------------------------------------------------------ signals
# net, ESP32 header pin, (connector, pin), direction, domain
SIGNALS = [
    ("FG23_SCLK",  "J1_18", ("CON2", p201_pin(12)), "in",    "3V3"),
    ("FG23_MOSI",  "J1_17", ("CON2", p201_pin(7)),  "in",    "3V3"),
    ("FG23_CS",    "J1_16", ("CON2", p201_pin(10)), "in",    "3V3"),
    ("FG23_CMD",   "J1_19", ("CON2", p201_pin(8)),  "out",   "3V3"),
    # RDY is an ESP32 OUTPUT: the ESP32 is the SPI slave and has to arm its
    # DMA before the FG23 may clock the next block out.  See
    # claude/FG23-kijelzopanel-valasztas-2026-08-17.md ("RDY (ki)", "CMD (ki)").
    ("FG23_RDY",   "J1_20", ("CON2", p201_pin(6)),  "out",   "3V3"),
    ("FG23_SPARE", None,    ("CON2", p201_pin(4)),  "spare", "3V3"),
    ("SWDIO",      "J3_10", ("CON2", p201_pin(18)), "bidir", "3V3"),
    ("SWCLK",      "J3_9",  ("CON2", p201_pin(20)), "out",   "3V3"),
    ("SWO",        "J3_16", ("CON2", p201_pin(16)), "in",    "3V3"),
    ("RESETn",     "J3_8",  ("CON1", p200_pin(4)),  "out",   "3V3"),
    ("I2C_SDA",    "J3_7",  ("CON1", 40), "bidir", "3V3"),
    ("I2C_SCL",    "J3_6",  ("CON1", 39), "out",   "3V3"),
    ("3V3_RADIO",  None,    ("CON1", 1),  "power", "3V3"),
    ("VMCU_IN",    None,    ("CON2", 2),  "power", "3V3"),
]

# every signal leaving at the socket needs exactly one cut point
CUT_POINTS = {
    "FG23_SCLK": "R2", "FG23_MOSI": "R1", "FG23_CS": "R3",
    "FG23_CMD": "R4", "FG23_RDY": "R5", "VMCU_IN": "R8",
    "3V3_RADIO": "JP1", "RESETn": "JP2", "I2C_SCL": "JP3",
    "I2C_SDA": "JP4", "FG23_SPARE": "JP5", "SWO": "JP6",
    "SWDIO": "JP7", "SWCLK": "JP8",
}

# ---------------------------------------------------- ESP32-S3 pin rules
ESP_GPIO = {
    "J1_1": "3V3", "J1_2": "3V3", "J1_3": "RST",
    "J1_4": 4, "J1_5": 5, "J1_6": 6, "J1_7": 7, "J1_8": 15, "J1_9": 16,
    "J1_10": 17, "J1_11": 18, "J1_12": 8, "J1_13": 3, "J1_14": 46,
    "J1_15": 9, "J1_16": 10, "J1_17": 11, "J1_18": 12, "J1_19": 13,
    "J1_20": 14, "J1_21": "5V0", "J1_22": "GND",
    "J3_1": "GND", "J3_2": 43, "J3_3": 44, "J3_4": 1, "J3_5": 2,
    "J3_6": 42, "J3_7": 41, "J3_8": 40, "J3_9": 39, "J3_10": 38,
    "J3_11": 37, "J3_12": 36, "J3_13": 35, "J3_14": 0, "J3_15": 45,
    "J3_16": 48, "J3_17": 47, "J3_18": 21, "J3_19": 20, "J3_20": 19,
    "J3_21": "GND", "J3_22": "GND",
}

FORBIDDEN = {
    33: "octal PSRAM (N16R8)", 34: "octal PSRAM (N16R8)",
    35: "octal PSRAM (N16R8)", 36: "octal PSRAM (N16R8)",
    37: "octal PSRAM (N16R8)",
    26: "SPI flash", 27: "SPI flash", 28: "SPI flash", 29: "SPI flash",
    30: "SPI flash", 31: "SPI flash", 32: "SPI flash",
    19: "native USB D-", 20: "native USB D+",
}

STRAPPING = {
    0: "BOOT, must be high at reset",
    3: "JTAG source select",
    45: "VDD_SPI voltage select, must be low at reset",
    46: "ROM message printing, must be low at reset",
}

IOMUX_FSPI = {10: "FSPICS0", 11: "FSPID", 12: "FSPICLK",
              13: "FSPIQ", 14: "FSPIWP"}

ADC1 = {1: "ADC1_CH0", 2: "ADC1_CH1", 3: "ADC1_CH2", 4: "ADC1_CH3",
        5: "ADC1_CH4", 6: "ADC1_CH5", 7: "ADC1_CH6", 8: "ADC1_CH7",
        9: "ADC1_CH8", 10: "ADC1_CH9"}

# ------------------------------------------------------- display (DISP2)
TFT = {
    1: ("VSS", "GND"), 2: ("VDD", "5V0"), 40: ("VSS", "GND"),
    21: ("RESET", "TFT_RST"), 22: ("TE", "TFT_TE"),
    23: ("LCD_CS", "TFT_CS"), 24: ("SCL", "TFT_SCK"),
    25: ("D/C", "TFT_DC"), 26: ("RD", "3V3"),
    27: ("LCD_SDI", "TFT_MOSI"), 28: ("LCD_SDO", "TFT_MISO"),
    29: ("BL_ON", "TFT_BL"),
    30: ("RTP_CS / CTP_SCL", "TCH_A"),
    31: ("RTP_PEN / CTP_SDA", "TCH_B"),
    32: ("SDO aux", "TFT_MISO"), 33: ("SCL aux", "TFT_SCK"),
    34: ("SDI aux", "TFT_MOSI"),
    39: ("FLASH_HOLD / CTP_INT", "TCH_INT"),
}

# ---------------------------------------------------------- button ladders
# node, ADC pin, pull-up, series filter R, filter C, [(switch, R to GND)]
LADDERS = [
    ("BTN_B", "J3_5", 10000.0, 1000.0, 100e-9,
     [("SW1", 0.0), ("SW2", 2200.0), ("SW3", 6800.0), ("SW4", 22000.0)]),
    ("BTN_A", "J3_4", 10000.0, 1000.0, 100e-9,
     [("SW5", 0.0), ("SW6", 2200.0)]),
]
VDD_LADDER = 3.3
ADC_FS = 3.1          # ESP32-S3 ADC full scale with 12 dB attenuation

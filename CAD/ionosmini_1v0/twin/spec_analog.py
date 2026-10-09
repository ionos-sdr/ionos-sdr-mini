# -*- coding: utf-8 -*-
"""Analog specification: the numbers layer 3 simulates against.

SOURCES
  [SCH]   our own schematic values (netlist), read at run time
  [PCB]   routed track length per net, read at run time from the board
  [STACK] stackup ASSUMED - the .kicad_pcb has no stackup block, so a
          standard 1.6 mm four-layer build is assumed and MUST be confirmed
          with the fab before this layer's impedance numbers mean anything
  [ESP]   ESP32-S3 datasheet: ADC full scale, GPIO drive
  [FG23]  EFR32FG23 datasheet: GPIO drive strength
  [LDO]   LP5907 datasheet
  [I2C]   NXP UM10204 I2C-bus specification, rise-time limits
  [LINK]  claude/FG23-SDR-allapot-2026-07-31.md - SPI_HZ now 4 MHz,
          12 MHz planned, 30 MHz is the PCB target for 700 ksps
"""

# ------------------------------------------------------------- [STACK]
# rev-B3-2L: JLCPCB 2-layer FR-4 1.6 mm, also written into the .kicad_pcb stackup block:
#   F.Cu 35 um | FR-4 core 1.53 mm | B.Cu 35 um                   total ~1.6 mm
# No plane: every track is a microstrip over the GND pour on the OTHER layer, 1.53 mm away.
# er 4.5 is an ASSUMPTION - JLC publishes no er for its 2-layer FR-4 (its impedance
# calculator starts at 4 layers). Treat the Z0 below as +-5 %, not as a measured fact.
STACKUP_ASSUMED = True
STACKUP = {
    "er": 4.5,                 # FR-4 core, assumed
    "er_core": 4.5,
    "h_f_in1_mm": 1.53,        # microstrip height: F.Cu over the B.Cu GND pour (and B.Cu over F.Cu)
    "h_in2_b_mm": 1.53,        # (no inner layer on this board)
    "core_mm": 1.53,
    "t_cu_mm": 0.035,
    "t_cu_inner_mm": 0.035,
    "total_mm": 1.60,
    "source": "JLCPCB 2-layer FR-4 1.6 mm (er assumed 4.5)",
}
# the line types the board really has, for the line report (twin_analog)
LINE_LAYERS = (("F.Cu", "microstrip over the B.Cu GND pour"),
               ("B.Cu", "microstrip over the F.Cu GND pour"))
TRACK_W_MM = 0.25              # [PCB] every signal track on this board


def microstrip_z0(w, h, t, er):
    """Hammerstad-Jensen, good to a few percent for w/h ~ 1."""
    import math
    # effective width correction for conductor thickness
    we = w + (t / math.pi) * (1.0 + math.log(2.0 * h / t))
    ee = (er + 1) / 2.0 + (er - 1) / 2.0 * (1.0 + 12.0 * h / we) ** -0.5
    u = we / h
    if u <= 1.0:
        z0 = 60.0 / math.sqrt(ee) * math.log(8.0 / u + u / 4.0)
    else:
        z0 = 120.0 * math.pi / (math.sqrt(ee) * (u + 1.393 + 0.667
                                                 * math.log(u + 1.444)))
    return z0, ee


def line_params(h_mm):
    """(Z0 ohm, propagation delay ps/mm) for our 0.25 mm track over h_mm."""
    import math
    z0, ee = microstrip_z0(TRACK_W_MM, h_mm, STACKUP["t_cu_mm"], STACKUP["er"])
    tpd_ps_per_mm = math.sqrt(ee) / 299.792458 * 1000.0
    return z0, tpd_ps_per_mm


# capacitance per mm of our track, from Z0 and velocity: C = tpd / Z0
def line_c_pf_per_mm(h_mm):
    z0, tpd = line_params(h_mm)
    return (tpd * 1e-12) / z0 * 1e12


# --------------------------------------------------------------- drivers
DRIVERS = {
    # name:        (source resistance ohm, rise time s, supply V)
    "FG23_GPIO":   (45.0, 2.0e-9, 3.3),     # [FG23] standard drive
    "ESP32_GPIO":  (40.0, 2.0e-9, 3.3),     # [ESP]
    "ESP32_OD":    (40.0, 4.0e-9, 3.3),     # open drain, pulls low only
}
PIN_C_PF = 5.0            # receiver pin capacitance, both sides
CONN_C_PF = 1.0           # one mezzanine contact

# ------------------------------------------------------------- the link
SPI_HZ_NOW = 4.0e6        # [LINK] what runs today
SPI_HZ_TARGET = 30.0e6    # [LINK] 700 ksps x 32 bit = 22.4 Mbit/s
SERIES_CANDIDATES = [0.0, 22.0, 33.0, 47.0, 68.0, 82.0]   # 2L: Z0 ~128 ohm, the match sits near Z0 - Rdrv ~ 83 ohm
OVERSHOOT_LIMIT = 0.30    # fraction of VDD we are willing to see at the pin
SETTLE_FRACTION = 0.10    # settled = within 10 % of final

# ---------------------------------------------------------------- I2C
I2C_PULLUP_OHM = 4700.0   # [SCH] R6 / R7 on the radio-board side
I2C_DEVICE_C_PF = 10.0    # per device: ESP32 pin, SSD1306, M24C02
I2C_DEVICES = 3
I2C_RISE_LIMIT = {100e3: 1000e-9, 400e3: 300e-9}   # [I2C] UM10204

# ---------------------------------------------------------------- LDO
LDO = {
    "part": "LP5907MFX-3.3",
    "vout": 3.3,
    "cout_uf": 1.0 + 0.1 + 0.1,     # [SCH] C3 1u + C4 100n + C8 100n
    "cin_uf": 1.0,                  # [SCH] C2
    "esr_ohm": 0.005,
    "bandwidth_hz": 40e3,           # [LDO] loop bandwidth, order of magnitude
    "load_step_a": 0.050,           # FG23 TX burst
    "droop_limit_v": 0.10,          # what the FG23 may see
}

# ------------------------------------------------------------- ADC
ADC_FS = 3.1              # [ESP] 12 dB attenuation
ADC_SAMPLE_US = 10.0      # how long after the key press we sample


def stripline_asym_z0(w, h_near, h_far, t, er):
    """IPC-2141A asymmetric stripline: trace at h_near from one plane and
    h_far from the other (both measured to the trace's nearer face)."""
    import math
    z_sym = 60.0 / math.sqrt(er) * math.log(1.9 * (2 * h_near + t) / (0.8 * w + t))
    return 80.0 / math.sqrt(er) * math.log(1.9 * (2 * h_near + t) / (0.8 * w + t)) * \
        (1.0 - h_near / (4.0 * (h_near + h_far + t))), z_sym


def layer_line_params(layer, w=None):
    """(Z0 ohm, delay ps/mm) for a track of width w on the named copper layer."""
    import math
    w = TRACK_W_MM if w is None else w
    s = STACKUP
    # IPC-2141A is ~3-5 % low here: the 2-D Laplace solver of the openEMS twin gives
    # 50.7-51.8 ohm for 0.25 mm on this geometry (er 4.6 / 4.4 bounds), IPC 49.3 ohm.
    if layer in ("In2.Cu", "SIG", "In1.Cu", "GND", "GND_PWR"):
        z0, _ = stripline_asym_z0(w, s["h_in2_b_mm"], s["core_mm"],
                                  s["t_cu_inner_mm"], s["er"])
        er_eff = (s["er"] * s["h_in2_b_mm"] + s["er_core"] * s["core_mm"]) / \
            (s["h_in2_b_mm"] + s["core_mm"])          # buried: no air at all
        return z0, math.sqrt(er_eff) / 299.792458 * 1000.0
    z0, ee = microstrip_z0(w, s["h_f_in1_mm"], s["t_cu_mm"], s["er"])
    return z0, math.sqrt(ee) / 299.792458 * 1000.0

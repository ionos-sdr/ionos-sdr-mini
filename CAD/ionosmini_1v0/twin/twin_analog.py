# -*- coding: utf-8 -*-
"""ionos-sdr-mini digital twin, layer 3: the analog layer.

Layers 1, 2 and 4 ask "is it connected, and does it fit".  This one asks
"will the signal survive the trip" - with the REAL routed track lengths
taken out of the .kicad_pcb, not a guess.

It builds SPICE decks, runs them through the ngspice that ships inside
KiCad (nothing to install), and checks the results against spec_analog.py.
Every deck is also written to twin/spice/*.cir so it can be opened in
QucsStudio or KiCad's own simulator and poked at by hand.

What it covers
  1. the FG23 SPI link at the 30 MHz PCB target - and what R1..R5 should be
  2. I2C rise time on the BOARD_ID bus
  3. the button ladders: level separation and settling at the ADC
  4. the 3V3_RADIO LDO under a transmit load step

Usage:  kicad-python twin_analog.py [path\\to\\board.kicad_pcb]
"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_analog as A
import spec_signals as S
from ngspice import Spice, write_deck

import pcbnew

PRJ = os.path.dirname(HERE)
DEFAULT_PCB = os.path.join(PRJ, "ionosSDR_mini.kicad_pcb")
DECKDIR = os.path.join(HERE, "spice")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
log = []
MM = pcbnew.ToMM


def say(level, group, msg):
    log.append((level, group, msg))


# ------------------------------------------------------- board geometry
def track_lengths(board):
    """Routed length and layer mix per net, straight from the copper."""
    out = {}
    for t in board.GetTracks():
        n = t.GetNetname()
        d = out.setdefault(n, {"mm": 0.0, "vias": 0, "layers": set(), "per_layer": {}})
        if t.Type() == pcbnew.PCB_VIA_T:
            d["vias"] += 1
        else:
            d["mm"] += MM(t.GetLength())
            ln = board.GetLayerName(t.GetLayer())
            d["layers"].add(ln)
            d["per_layer"][ln] = d["per_layer"].get(ln, 0.0) + MM(t.GetLength())
    return out


def net_length(tl, *names):
    mm = 0.0
    vias = 0
    for n in names:
        if n in tl:
            mm += tl[n]["mm"]
            vias += tl[n]["vias"]
    return mm, vias


# ------------------------------------------------------------- the decks
def deck_spi(length_mm, rs, freq, z0, tpd_ps_mm):
    """FG23 drives, ESP32 listens, through our real trace."""
    td = length_mm * tpd_ps_mm * 1e-12
    per = 1.0 / freq
    drv_r, tr, vdd = A.DRIVERS["FG23_GPIO"]
    cl = (A.PIN_C_PF + A.CONN_C_PF) * 1e-12
    return [
        ".title FG23 SPI link, %.0f mm, Rs=%.0f ohm, %.0f MHz"
        % (length_mm, rs, freq / 1e6),
        "Vdrv src 0 PULSE(0 %.2f 0 %.2gn %.2gn %.4gn %.4gn)"
        % (vdd, tr * 1e9, tr * 1e9, per / 2 * 1e9, per * 1e9),
        "Rdrv src a %.3f" % drv_r,
        "Rs a b %.3f" % max(rs, 1e-3),
        "Tline b 0 c 0 Z0=%.2f TD=%.4gn" % (z0, td * 1e9),
        "Cload c 0 %.3fp" % (cl * 1e12),
        ".tran %.4gn %.4gn 0 %.4gn" % (per / 400 * 1e9, per * 6 * 1e9,
                                       per / 800 * 1e9),
        ".end",
    ]


def deck_i2c(cbus_f, rp):
    tr_limit = max(A.I2C_RISE_LIMIT.values())
    return [
        ".title I2C rise time, Cbus=%.1f pF, Rp=%.0f ohm" % (cbus_f * 1e12, rp),
        "Vdd vdd 0 3.3",
        "Rp vdd sda %.1f" % rp,
        "Cb sda 0 %.4gp" % (cbus_f * 1e12),
        # open-drain driver: on until 100 ns, then released
        "Sw sda 0 ctl 0 SWMOD",
        "Vctl ctl 0 PULSE(3.3 0 100n 1n 1n 5u 10u)",
        ".model SWMOD SW(Ron=20 Roff=1e9 Vt=1.65 Vh=0.1)",
        ".tran 2n %.4gu" % (max(tr_limit * 8, 4e-6) * 1e6),
        ".end",
    ]


def deck_ladder(node, pull, rser, cf, sw_r, rtrace):
    return [
        ".title button ladder %s, switch R=%.0f ohm" % (node, sw_r),
        "Vdd vdd 0 3.3",
        "Rpu vdd n1 %.1f" % pull,
        "Rtr n1 n2 %.4f" % max(rtrace, 1e-4),
        "Rsw n2 0 %.4f" % max(sw_r, 1e-3),
        "Rs n2 adc %.1f" % rser,
        "Cf adc 0 %.4gn" % (cf * 1e9),
        "Radc adc 0 1e12",
        ".ic v(adc)=3.3",
        ".tran 1u 20m",
        ".end",
    ]


def deck_ldo(cout_f, step_a, esr):
    return [
        ".title LP5907 output under a %.0f mA load step" % (step_a * 1e3),
        "Vref ref 0 3.3",
        # the regulator as a controlled source with finite loop bandwidth:
        # a first-order block of output impedance Rout in series with L
        "Eout drv 0 ref 0 1.0",
        "Rout drv out 0.05",
        "Lout out out2 1.0u",
        "Cout out2 esr %.4gu" % (cout_f * 1e6),
        "Resr esr 0 %.4f" % esr,
        "Iload out2 0 PULSE(0 %.4g 10u 20n 20n 200u 400u)" % step_a,
        ".tran 100n 120u",
        ".end",
    ]


# ------------------------------------------------------------- the checks
def check_spi(sp, board, tl):
    # rev-B3 layer roles: F.Cu GND copper, In1 signal, In2 GND+power, B.Cu signal
    for lay, what in (("In1.Cu", "asymmetric stripline, near plane F.Cu GND copper"),
                      ("B.Cu", "microstrip over In2 GND/power")):
        z, d_ = A.layer_line_params(lay)
        say(PASS, "line", "0.25 mm on %-6s (%s): Z0 = %.1f ohm, %.2f ps/mm  [%s]"
            % (lay, what, z, d_, A.STACKUP.get("source", "ASSUMED")))
    worst = {}
    for net in ("FG23_SCLK", "FG23_MOSI", "FG23_CS", "FG23_CMD", "FG23_RDY"):
        mm, vias = net_length(tl, net, net + "_RB")
        if mm <= 0:
            say(WARN, "spi", "%s has no routed copper" % net)
            continue
        per = {}
        for nn in (net, net + "_RB"):
            for ln, v in tl.get(nn, {}).get("per_layer", {}).items():
                per[ln] = per.get(ln, 0.0) + v
        main = max(per, key=per.get) if per else "F.Cu"
        z0, tpd = A.layer_line_params(main)
        td = mm * tpd
        say(PASS, "spi", "%-10s %6.1f mm, %d vias, %.0f%% on %s (Z0 %.1f ohm), "
            "one-way delay %.0f ps"
            % (net, mm, vias, 100.0 * per.get(main, 0) / max(mm, 1e-9), main, z0, td))
        for f in (A.SPI_HZ_NOW, A.SPI_HZ_TARGET):
            best = None
            table = []
            for rs in A.SERIES_CANDIDATES:
                d = deck_spi(mm, rs, f, z0, tpd)
                write_deck(os.path.join(DECKDIR, "spi_%s_%.0fMHz_R%.0f.cir"
                                        % (net, f / 1e6, rs)), d)
                try:
                    r = sp.run(d)
                except Exception as e:
                    say(WARN, "spi", "%s %.0f MHz Rs=%.0f: %s"
                        % (net, f / 1e6, rs, e))
                    continue
                v = r.get("c") or r.get("v(c)")
                if not v:
                    continue
                vdd = A.DRIVERS["FG23_GPIO"][2]
                over = (max(v) - vdd) / vdd
                under = -min(v) / vdd
                worst_dev = max(over, under)
                table.append((rs, worst_dev))
                if best is None or worst_dev < best[0] - 1e-4:
                    best = (worst_dev, rs, over, under)
            if best is None or not table:
                continue
            dev, rs, over, under = best
            zero = dict(table).get(0.0, dev)
            worst.setdefault(f, []).append((net, rs, dev, zero))
            lvl = PASS if dev <= A.OVERSHOOT_LIMIT else FAIL
            say(lvl, "spi", "%-10s @%4.0f MHz: %s   -> best %.0f ohm "
                "(%.2f%% peak deviation, 0 ohm gives %.2f%%)"
                % (net, f / 1e6,
                   " ".join("%.0fR:%.2f%%" % (a, b * 100) for a, b in table),
                   rs, dev * 100, zero * 100))
    for f, rows in sorted(worst.items()):
        rs = max(r[1] for r in rows)
        zero_ok = all(z <= A.OVERSHOOT_LIMIT for n, r_, d, z in rows)
        gain = max(z - d for n, r_, d, z in rows)
        if zero_ok and gain < 0.02:
            say(PASS, "spi", "RECOMMENDATION at %.0f MHz: leave R1..R5 at "
                "0 ohm - the FG23's own %.0f ohm output already damps this "
                "%.0f ohm line, series resistors buy %.1f%% at best"
                % (f / 1e6, A.DRIVERS["FG23_GPIO"][0], z0, gain * 100))
        else:
            say(WARN, "spi", "RECOMMENDATION at %.0f MHz: fit R1..R5 = %.0f "
                "ohm (improves the worst net by %.1f%% of VDD)"
                % (f / 1e6, rs, gain * 100))


def check_i2c(sp, board, tl):
    cpm = A.line_c_pf_per_mm(A.STACKUP["h_f_in1_mm"])
    for net in ("I2C_SCL", "I2C_SDA"):
        mm, vias = net_length(tl, net, net + "_RB")
        cbus = (mm * cpm + A.I2C_DEVICES * A.I2C_DEVICE_C_PF
                + A.CONN_C_PF) * 1e-12
        d = deck_i2c(cbus, A.I2C_PULLUP_OHM)
        write_deck(os.path.join(DECKDIR, "i2c_%s.cir" % net), d)
        try:
            r = sp.run(d)
        except Exception as e:
            say(WARN, "i2c", "%s: %s" % (net, e))
            continue
        t = r.get("time")
        v = r.get("sda") or r.get("v(sda)")
        if not (t and v):
            continue
        lo, hi = 0.3 * 3.3, 0.7 * 3.3
        t1 = t2 = None
        for i in range(len(t)):
            if t[i] < 100e-9:
                continue
            if t1 is None and v[i] >= lo:
                t1 = t[i]
            if t1 is not None and v[i] >= hi:
                t2 = t[i]
                break
        if t1 is None or t2 is None:
            say(FAIL, "i2c", "%s never reaches 70%% of VDD" % net)
            continue
        tr = t2 - t1
        say(PASS, "i2c", "%-8s %6.1f mm -> Cbus %.0f pF, tr(30-70%%) = %.0f ns"
            % (net, mm, cbus * 1e12, tr * 1e9))
        for f, lim in sorted(A.I2C_RISE_LIMIT.items()):
            lvl = PASS if tr <= lim else FAIL
            say(lvl, "i2c", "   %s at %3.0f kHz (limit %.0f ns)"
                % ("fits" if lvl == PASS else "TOO SLOW", f / 1e3, lim * 1e9))


def check_ladders(sp, board, tl):
    cpm = A.line_c_pf_per_mm(A.STACKUP["h_f_in1_mm"])
    for node, adcpin, pu, rser, cf, sw in S.LADDERS:
        mm, vias = net_length(tl, node)
        levels = []
        for name, r in [("idle", 1e12)] + list(sw):
            d = deck_ladder(node, pu, rser, cf, r, 0.02 * mm)
            write_deck(os.path.join(DECKDIR, "ladder_%s_%s.cir"
                                    % (node, name)), d)
            try:
                res = sp.run(d)
            except Exception as e:
                say(WARN, "ladder", "%s/%s: %s" % (node, name, e))
                continue
            v = res.get("adc") or res.get("v(adc)")
            if v:
                levels.append((name, v[-1]))
        if len(levels) < 2:
            continue
        levels.sort(key=lambda t: t[1])
        gaps = [levels[i + 1][1] - levels[i][1] for i in range(len(levels) - 1)]
        say(PASS, "ladder", "%s (%.0f mm, %.0f pF of trace): %s"
            % (node, mm, mm * cpm,
               ", ".join("%s=%.3fV" % (n, v) for n, v in levels)))
        g = min(gaps)
        lvl = PASS if g >= 0.4 else (WARN if g >= 0.25 else FAIL)
        say(lvl, "ladder", "%s smallest gap %.3f V (ADC full scale %.1f V, "
            "12 bit LSB %.1f mV)" % (node, g, A.ADC_FS, A.ADC_FS / 4096 * 1000))


def check_ldo(sp, board, tl):
    L = A.LDO
    d = deck_ldo(L["cout_uf"] * 1e-6, L["load_step_a"], L["esr_ohm"])
    write_deck(os.path.join(DECKDIR, "ldo_load_step.cir"), d)
    try:
        r = sp.run(d)
    except Exception as e:
        say(WARN, "ldo", "%s" % e)
        return
    v = r.get("out2") or r.get("v(out2)")
    if not v:
        say(WARN, "ldo", "no output vector")
        return
    droop = L["vout"] - min(v)
    over = max(v) - L["vout"]
    lvl = PASS if droop <= L["droop_limit_v"] else FAIL
    say(lvl, "ldo", "%s, Cout %.2f uF: %.0f mA step -> %.0f mV droop, "
        "%.0f mV overshoot (limit %.0f mV)"
        % (L["part"], L["cout_uf"], L["load_step_a"] * 1e3, droop * 1e3,
           over * 1e3, L["droop_limit_v"] * 1e3))
    mm, vias = net_length(tl, "3V3_RADIO", "3V3_RADIO_RB", "VMCU_IN")
    # 0.25 mm track, 35 um copper: about 2 mohm per mm
    rdc = 0.002 * mm
    say(PASS if rdc * L["load_step_a"] < 0.02 else WARN, "ldo",
        "3V3_RADIO + VMCU_IN copper: %.0f mm -> %.1f mohm -> %.1f mV IR drop "
        "at %.0f mA" % (mm, rdc * 1e3, rdc * L["load_step_a"] * 1e3,
                        L["load_step_a"] * 1e3))


# ======================================================================
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = args[0] if args else DEFAULT_PCB
    if not os.path.exists(path):
        print("board not found: %s" % path)
        return 2
    os.makedirs(DECKDIR, exist_ok=True)
    board = pcbnew.LoadBoard(path)
    tl = track_lengths(board)
    try:
        sp = Spice()
    except Exception as e:
        print("ngspice not available: %s" % e)
        print("the decks are still written to %s" % DECKDIR)
        return 2

    print("=" * 76)
    print(" ionos-sdr-mini digital twin - layer 3: analog")
    print(" board  : %s" % path)
    print(" ngspice: %s" % sp.path)
    print(" decks  : %s" % DECKDIR)
    print("=" * 76)

    check_spi(sp, board, tl)
    check_i2c(sp, board, tl)
    check_ladders(sp, board, tl)
    check_ldo(sp, board, tl)

    groups = {}
    for lvl, grp, msg in log:
        groups.setdefault(grp, []).append((lvl, msg))
    titles = [("line", "the transmission line our tracks really are"),
              ("spi", "the FG23 link at speed"),
              ("i2c", "BOARD_ID bus rise time"),
              ("ladder", "button ladders at the ADC"),
              ("ldo", "the 3V3_RADIO rail")]
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
    if A.STACKUP_ASSUMED:
        print(" NOTE: the stackup is assumed, not read from the board - the")
        print("       impedance and rise-time numbers are only as good as that.")
    print("=" * 76)
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

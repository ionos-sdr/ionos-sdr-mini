#!/usr/bin/env python3
# VSG run over the full coverage, 2026-11-12. VSG60 -> long coax -> 30 dB pad -> BRD4265B (434 MHz match).
# P_in = VSG level - 30 dB (pad nominal; the long coax is NOT subtracted - calibrate it with the BB60C).
# B<kHz> (no crystal correction) -> the tone sits at +20 kHz + 4.2 ppm*f. Each point is checked with the
# VSG output off as well, so an on-board comb line can never be mistaken for the VSG tone.
#  1: gain / noise / NF / MDS, 5 MHz grid 97-3100 MHz, adaptive level
#  2: linearity at 145 / 434 / 868 / 1296 / 2400 MHz (VSG +10 .. -100 dBm)
#  3: 2-FSK 5 kbps BER 1e-2 at 145 / 434 / 868 / 1296 / 2400 MHz
#  4: gain / NF on a 1 MHz grid 97-1562 MHz
import os, time, numpy as np, serial
from vsg60 import VSG
from soapyio import *
import fsk_lib
PAD = 30.0; ARB = os.path.abspath("fsk_prbs9_100k.binfc"); FS = 200000; N = 1 << 15
DIV = [1,2,3,4,5,6,7,8,9,10,12,14,15,16,18,20,21,24]
LO  = [4050,4050,4100,4050,4200,4100,4800,4650,4550,4500,4100,4750,4350,4650,4550,4500,4750,4650]
HI  = [6200,6250,6000,6250,5900,6000,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250]
def reachable(khz): return any(LO[i]*1000 <= 2*d*khz <= HI[i]*1000 for i, d in enumerate(DIV))
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0); set_rate(FS)
def B(khz): r = cmd("B%d" % khz, 1.0); time.sleep(0.4); return r
def tone(fexp, span=8e3, secs=1.0):
    z, _ = capture(secs)
    if len(z) < N: return None
    S = spectrum(z, N); f = (np.arange(N) - N // 2) * FS / N
    idx = np.where(np.abs(f - fexp) <= span)[0]; k = idx[np.argmax(S[idx])]
    return 10 * np.log10(S[k-4:k+5].sum() / 1.7 + 1e-20), f[k], noise_dbfs_hz(S, FS, N)
def gain_point(v, fh, tag):
    fexp = 20e3 + 4.2e-6 * fh
    B(int(fh // 1000)); v.freq(fh + 20e3, verify=False)
    v.off(); time.sleep(1.4); off = tone(fexp)
    if off is None: fg23_reset(); csvw(tag, [int(fh), "nodata"]); return
    v.on()
    for lv in (-40, -10, 10):
        v.power(lv); time.sleep(1.6); on = tone(fexp)
        if on is None: break
        if on[0] - off[0] > 15 or lv == 10: break
    if on is None: fg23_reset(); csvw(tag, [int(fh), "nodata"]); return
    pin = lv - PAD; g = on[0] - pin; nd_in = on[2] - g
    csvw(tag, [int(fh), lv, "%.1f" % pin, "%.2f" % on[0], "%.2f" % off[0], "%.0f" % (on[1] - 20e3),
               "%.2f" % on[2], "%.2f" % g, "%.1f" % (nd_in + 174), "%.1f" % (nd_in + 10*np.log10(500) + 10)])
log("VSGFULL start, pad %.1f dB (coax not subtracted)" % PAD); set_rate(FS)
z = fsk_lib.gen(100000, 40); fsk_lib.write_binfc(ARB, z)
with VSG(port=5124) as v:
    try:
        log("VSG %s" % v.idn()); v.modulation(False)
        for fk in [k for k in range(97000, 3100001, 5000) if reachable(k)]:
            gain_point(v, fk * 1000.0, "v_gain")
        log("1 done; sensors %s" % sensors())
        v.on()
        for fm in (145, 434, 868, 1296, 2400):
            fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh + 20e3, verify=False); fexp = 20e3 + 4.2e-6 * fh
            for lv in range(10, -101, -5):
                v.power(lv); time.sleep(1.6); t = tone(fexp); z, _ = capture(0.3)
                mz = float(np.max(np.abs(z))) if len(z) else float("nan")
                csvw("v_lin", [fm, lv, "%.1f" % (lv - PAD)] + (["%.2f" % t[0], "%.2f" % t[2]] if t else ["nan", "nan"]) + ["%.3f" % mz])
        log("2 done")
        okl, msg = v.load_arb(ARB, srate_hz=100000); log("arb load: %s %s" % (okl, msg))
        if okl:
            for fm in (145, 434, 868, 1296, 2400):
                fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh, verify=False); time.sleep(1.0)
                lo, hi = -140.0, -20.0; pts = []
                for _ in range(9):
                    mid = (lo + hi) / 2; v.power(min(10.0, mid + PAD)); time.sleep(1.6)
                    zz, _ = capture(1.2); e = fsk_lib.ber(zz, 50000)[0] if len(zz) > 20000 else 0.5; pts.append((mid, e))
                    if e > 1e-2: lo = mid
                    else: hi = mid
                csvw("v_fsk", [fm, "%.1f" % hi] + ["%.1f:%.4f" % p for p in pts])
            v.modulation(False)
        log("3 done")
        for fk in [k for k in range(97000, 1562001, 1000) if reachable(k)]:
            gain_point(v, fk * 1000.0, "v_gain1")
        log("4 done; sensors %s" % sensors())
        v.off(); v.modulation(True)
    finally:
        v.off(); v.modulation(True); log("VSG off")
log("VSGFULL end")

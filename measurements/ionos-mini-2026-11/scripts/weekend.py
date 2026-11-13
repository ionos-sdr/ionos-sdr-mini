#!/usr/bin/env python3
# Long characterisation run, 2026-11-12 22:45 -> Mon 2026-11-16 07:00.
# VSG60 -> long coax -> 30 dB pad -> BRD4265B (434 MHz match). P_in = VSG - 30 dB (coax not subtracted).
# B<kHz> (no crystal correction); the VSG tone sits at +off + ppm*f. Every block logs and survives errors.
#  A  gain/NF/MDS 1 MHz grid 2025-3100 MHz (completes the 97-1562 grid of 11-12)
#  B  linearity / clip at 21 frequencies
#  C  2-FSK 5 kbps: BER 1e-2 level every 25 MHz; full BER-vs-level curves at 6 frequencies
#  D  two-tone IM3 (Arb, +-10 kHz) -> IIP3 at 6 frequencies
#  E  spurious responses: RX fixed at 145 / 434 / 868 MHz, VSG swept 30 MHz-6 GHz (5 MHz), -20 dBm at board
#  G  noise skirt / reciprocal mixing around a strong CW tone at 145 / 434 / 868 MHz
#  F  stability loop until Monday 07:00: gain, NF, frequency error at 12 reference frequencies every cycle
import os, time, datetime as dt, traceback, numpy as np, serial
from vsg60 import VSG
from soapyio import *
import fsk_lib
PAD = 30.0; FS = 200000; N = 1 << 15
ARB_FSK = os.path.abspath("fsk_prbs9_100k.binfc"); ARB_2T = os.path.abspath("twotone_10k_100k.binfc")
DIV = [1,2,3,4,5,6,7,8,9,10,12,14,15,16,18,20,21,24]
LO  = [4050,4050,4100,4050,4200,4100,4800,4650,4550,4500,4100,4750,4350,4650,4550,4500,4750,4650]
HI  = [6200,6250,6000,6250,5900,6000,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250]
PPM = 5.0e-6                                       # uncorrected crystal error seen on 11-12 (search window is +-8 kHz)
END = dt.datetime(2026, 11, 16, 7, 0)

import subprocess
class RVSG:
    """VSG60 with self-healing: if the VSG software drops the SCPI link or dies (seen 11-12 23:19),
    restart VSG.exe, reconnect and re-apply the last state (arb, modulation, freq, power, output)."""
    EXE = r"C:\Program Files\Signal Hound\VSG\VSG.exe"
    def __init__(self):
        self.st = {"arb": None, "mod": False, "freq": None, "pow": None, "on": False}; self.v = None; self.restarts = 0; self._connect(False)
    def _connect(self, restart):
        if restart:
            self.restarts += 1; log("VSG link lost -> restarting VSG software (#%d)" % self.restarts)
            try: self.v.close()
            except Exception: pass
            subprocess.call(["taskkill", "/F", "/IM", "VSG.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3); subprocess.Popen([self.EXE]); time.sleep(25)
        for i in range(12):
            self.v = VSG(port=5124); idn = self.v.open_verified(probak=3)
            if idn: break
            time.sleep(10)
        log("VSG %s" % idn)
        if restart:
            st = self.st
            if st["arb"]: self.v.load_arb(st["arb"][0], srate_hz=st["arb"][1])
            self.v.modulation(st["mod"])
            if st["freq"]: self.v.freq(st["freq"], verify=False)
            if st["pow"] is not None: self.v.power(st["pow"])
            (self.v.on if st["on"] else self.v.off)()
    def _do(self, name, *a, **k):
        for attempt in range(3):
            try: return getattr(self.v, name)(*a, **k)
            except (OSError, ConnectionError, AttributeError) as e:
                log("VSG %s failed: %s" % (name, e)); self._connect(True)
        raise RuntimeError("VSG unrecoverable")
    def freq(self, f, verify=False): self.st["freq"] = f; return self._do("freq", f, verify=verify)
    def power(self, p): self.st["pow"] = p; return self._do("power", p)
    def on(self): self.st["on"] = True; return self._do("on")
    def off(self): self.st["on"] = False; return self._do("off")
    def modulation(self, m): self.st["mod"] = m; return self._do("modulation", m)
    def load_arb(self, path, srate_hz=100000):
        self.st["arb"] = (path, srate_hz); self.st["mod"] = True; return self._do("load_arb", path, srate_hz=srate_hz)
    def idn(self): return self._do("idn")
    def close(self):
        try: self.v.close()
        except Exception: pass

def reachable(khz): return any(LO[i]*1000 <= 2*d*khz <= HI[i]*1000 for i, d in enumerate(DIV))
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
def B(khz): r = cmd("B%d" % khz, 1.0); time.sleep(0.4); return r
def spec(secs=1.0, fs=FS, n=N):
    z, _ = capture(secs)
    if len(z) < n: fg23_reset(); set_rate(fs); return None
    S = spectrum(z, n); f = (np.arange(n) - n // 2) * fs / n
    return S, f, z
def tone_at(S, f, fexp, span=8e3):
    idx = np.where(np.abs(f - fexp) <= span)[0]; k = idx[np.argmax(S[idx])]
    return 10 * np.log10(S[max(k-4,0):k+5].sum() / 1.7 + 1e-20), f[k]
def gain_point(v, fh, tag, extra=()):
    fexp = 20e3 + PPM * fh; B(int(fh // 1000)); v.freq(fh + 20e3, verify=False)
    v.off(); time.sleep(1.4); r0 = spec()
    if r0 is None: csvw(tag, [int(fh), "nodata"] + list(extra)); return None
    off = tone_at(r0[0], r0[1], fexp); v.on(); on = None
    for lv in (-40, -10, 10):
        v.power(lv); time.sleep(1.6); r = spec()
        if r is None: break
        on = tone_at(r[0], r[1], fexp); nd = noise_dbfs_hz(r[0], FS, N)
        if on[0] - off[0] > 15 or lv == 10: break
    if on is None: csvw(tag, [int(fh), "nodata"] + list(extra)); return None
    pin = lv - PAD; g = on[0] - pin; nd_in = nd - g
    csvw(tag, [int(fh), lv, "%.1f" % pin, "%.2f" % on[0], "%.2f" % off[0], "%.0f" % (on[1] - 20e3), "%.2f" % nd,
               "%.2f" % g, "%.1f" % (nd_in + 174), "%.1f" % (nd_in + 10*np.log10(500) + 10)] + list(extra))
    return g
def block(name, fn, v):
    log("BLOCK %s start" % name)
    try: fn(v)
    except Exception: log("BLOCK %s FAILED:\n%s" % (name, traceback.format_exc()))
    finally:
        try: v.modulation(False)
        except Exception: pass
        log("BLOCK %s end; sensors %s (VSG restarts %d)" % (name, sensors(), v.restarts))
def A(v):
    for k in range(int(os.environ.get('A_START', '2025000')), 3100001, 1000):
        if reachable(k): gain_point(v, k * 1000.0, "w_gainA")
LINF = [100, 145, 220, 300, 350, 434, 500, 600, 700, 800, 868, 915, 1000, 1100, 1296, 1450, 2100, 2400, 2600, 2850, 3050]
def Bl(v):
    set_rate(FS); v.on()
    for fm in LINF:
        fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh + 20e3, verify=False); fexp = 20e3 + PPM * fh
        for lv in range(10, -106, -3):
            v.power(lv); time.sleep(1.5); r = spec(0.6)
            if r is None: continue
            t = tone_at(r[0], r[1], fexp)
            csvw("w_lin", [fm, lv, "%.1f" % (lv - PAD), "%.2f" % t[0], "%.2f" % noise_dbfs_hz(r[0], FS, N), "%.3f" % float(np.max(np.abs(r[2])))])
def fsk_level(v, fh):
    B(int(fh // 1000)); v.freq(fh, verify=False); time.sleep(1.0); lo, hi = -140.0, -20.0
    for _ in range(9):
        mid = (lo + hi) / 2; v.power(min(10.0, mid + PAD)); time.sleep(1.5)
        zz, _ = capture(1.2); e = fsk_lib.ber(zz, 50000)[0] if len(zz) > 20000 else 0.5
        if e > 1e-2: lo = mid
        else: hi = mid
    return hi
def C(v):
    set_rate(50000); ok, msg = v.load_arb(ARB_FSK, srate_hz=100000); log("arb %s %s" % (ok, msg)); v.on()
    for k in range(100000, 3100001, 25000):
        if reachable(k): csvw("w_fsk", [k, "%.1f" % fsk_level(v, k * 1000.0)])
    for fm in (145, 434, 868, 1296, 2400, 3000):
        fh = fm * 1e6; thr = fsk_level(v, fh)
        for p in np.arange(thr - 8, thr + 8.1, 1.0):
            v.power(min(10.0, p + PAD)); time.sleep(1.5); zz, _ = capture(3.0)
            e, nb = fsk_lib.ber(zz, 50000) if len(zz) > 20000 else (0.5, 0)
            csvw("w_bercurve", [fm, "%.1f" % p, "%.5f" % e, nb])
    set_rate(FS)
def D(v):
    set_rate(FS); ok, msg = v.load_arb(ARB_2T, srate_hz=100000); log("arb 2-tone %s %s" % (ok, msg)); v.on()
    for fm in (145, 434, 868, 1296, 2400, 3000):
        fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh + 40e3, verify=False); c = 40e3 + PPM * fh
        for lv in range(10, -80, -3):
            v.power(lv); time.sleep(1.5); r = spec(1.0)
            if r is None: continue
            S, f, _ = r
            t1, t2 = tone_at(S, f, c - 10e3, 2e3)[0], tone_at(S, f, c + 10e3, 2e3)[0]
            i1, i2 = tone_at(S, f, c - 30e3, 2e3)[0], tone_at(S, f, c + 30e3, 2e3)[0]
            csvw("w_im3", [fm, lv, "%.1f" % (lv - PAD - 3.0), "%.2f" % t1, "%.2f" % t2, "%.2f" % i1, "%.2f" % i2, "%.2f" % noise_dbfs_hz(S, FS, N)])
def E(v):
    set_rate(FS)
    for fm in (145, 434, 868):
        fh = fm * 1e6; B(int(fh // 1000)); v.off(); time.sleep(1.4); base = spec(1.0)
        bS = 10 * np.log10(base[0] + 1e-20); f = base[1]; med = np.median(bS); v.on()
        g = None
        v.freq(fh + 20e3, verify=False); v.power(-40); time.sleep(1.6); r = spec()
        if r is not None: g = tone_at(r[0], r[1], 20e3 + PPM * fh)[0] - (-40 - PAD)
        log("E %d MHz: in-band gain %.1f dB" % (fm, g if g else float('nan')))
        v.power(10)
        for fv in np.arange(30e6, 6000e6 + 1, 5e6):
            if abs(fv - fh) < 150e3: continue
            v.freq(fv, verify=False); time.sleep(1.4); r = spec(0.5)
            if r is None: continue
            Sd = 10 * np.log10(r[0] + 1e-20); m = np.median(Sd)
            d = (Sd - m) - (bS - med); d[np.abs(f) < 500] = -99; k = np.argmax(d)
            resp = Sd[k] - m
            lvl = tone_at(r[0], f, f[k], 1e3)[0]          # dBFS of the response
            rej = (lvl - g) - (10 - PAD) if (g and resp > 12) else float("nan")   # response re. the input level, dBc
            csvw("w_spur", [fm, int(fv), "%.1f" % resp, "%.0f" % f[k], "%.2f" % lvl, "%.1f" % rej])
def G(v):
    set_rate(FS); v.on()
    for fm in (145, 434, 868):
        fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh, verify=False); v.power(-35 if fm != 868 else -20); time.sleep(1.6)
        r = spec(4.0, FS, 1 << 16)
        if r is None: continue
        S, f, _ = r; Sd = 10 * np.log10(S + 1e-20); c = PPM * fh; k = np.argmin(np.abs(f - c)); car = Sd[k-6:k+7].max()
        rbw = FS / (1 << 16) * 1.73
        for off in (100, 300, 1e3, 3e3, 1e4, 3e4, 9e4):
            j = np.argmin(np.abs(f - (c + off))); lvl = np.median(Sd[max(j-3,0):j+4])
            csvw("w_pn", [fm, int(off), "%.1f" % (lvl - car - 10*np.log10(rbw))])
REF = [102, 145, 300, 434, 500, 700, 868, 1000, 1296, 1500, 2400, 3000]
def F(v):
    cyc = 0; set_rate(FS)
    while dt.datetime.now() < END:
        cyc += 1
        for fm in REF:
            gain_point(v, fm * 1e6, "w_stab", (cyc,))
        log("F cycle %d done; sensors %s" % (cyc, sensors()))
log("WEEKEND start; pad %.1f dB (coax not subtracted)" % PAD); set_rate(FS)
fsk_lib.write_binfc(ARB_FSK, fsk_lib.gen(100000, 40))
t = np.arange(100000) / 100000.0
fsk_lib.write_binfc(ARB_2T, (0.5 * (np.exp(2j*np.pi*10e3*t) + np.exp(-2j*np.pi*10e3*t))).astype(np.complex64))
v = RVSG()
try:
    v.modulation(False)
    for name, fn in (("A", A), ("B", Bl), ("C", C), ("D", D), ("E", E), ("G", G), ("F", F)):
        block(name, fn, v)
finally:
    try: v.off(); v.modulation(True); v.close()
    except Exception: pass
    log("WEEKEND end; VSG off")

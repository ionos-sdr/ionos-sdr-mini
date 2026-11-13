#!/usr/bin/env python3
# Full-coverage run #2, 2026-11-10: input TERMINATED (30 dB pad + 50 ohm). B<kHz> (no crystal
# correction) with the firmware's VCO-window divider choice; unreachable frequencies are skipped here
# (same window table as app.c), so a refused tune can't be mistaken for data.
#  A: 85-1625 + 2000-3125 MHz, 1 MHz steps   C: on-board comb (k x 19.5/39/40 MHz) as test signal
#  E: fine 200 kHz map 85-1625 MHz, then 2000-3125 MHz, until 23:00 or done
import time, datetime as dt, numpy as np, serial
from soapyio import *
FS = 200000; N = 1 << 13
DIV = [1,2,3,4,5,6,7,8,9,10,12,14,15,16,18,20,21,24]
LO  = [4050,4050,4100,4050,4200,4100,4800,4650,4550,4500,4100,4750,4350,4650,4550,4500,4750,4650]
HI  = [6200,6250,6000,6250,5900,6000,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250,6250]
def reachable(khz): return any(LO[i]*1000 <= 2*d*khz <= HI[i]*1000 for i, d in enumerate(DIV))
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
NRST = [0]
def point(khz, cap=1.2):
    r = cmd("B%d" % khz, 1.0); time.sleep(0.5); z, _ = capture(cap)
    if len(z) < 4096: fg23_reset(); NRST[0] += 1; set_rate(FS); return None, r
    S = spectrum(z, N); Sd = 10 * np.log10(S + 1e-20); med = np.median(Sd)
    f = (np.arange(N) - N // 2) * FS / N; peaks = []
    for k in np.argsort(Sd)[::-1]:
        if abs(f[k]) < 400: continue
        if all(abs(f[k] - p[0]) > 1500 for p in peaks): peaks.append((f[k], Sd[k] - med))
        if len(peaks) >= 5: break
    return dict(n=len(z), nd=noise_dbfs_hz(S, FS, N), peaks=peaks, dc=20*np.log10(abs(np.mean(z))+1e-12), S=Sd, f=f, med=med), r
def row(tag, khz, res, r):
    if res is None: csvw(tag, [khz, 0, "nodata", r.replace(",", ";")[:60]]); return
    csvw(tag, [khz, 0, res["n"], "%.2f" % res["nd"], "%.1f" % res["dc"]] + ["%+.0f:%.1f" % p for p in res["peaks"]])
set_rate(FS); log("FULLWB3 start (terminated input)")
grid = [k for k in list(range(85000, 1700001, 1000)) + list(range(1700000, 3300001, 5000)) if reachable(k)]
for khz in grid:
    res, r = point(khz); row("t_map", khz, res, r)
log("A done (%d pts), resets %d, sensors %s" % (len(grid), NRST[0], sensors()))
for base, kmax in ((19500, 170), (39000, 85), (40000, 83)):
    for k in range(2, kmax + 1):
        fk = base * k
        if not reachable(fk + 20): continue
        res, r = point(fk + 20)
        if res is None: csvw("t_comb", [base, k, fk, "nodata"]); continue
        sel = np.abs(res["f"] + 20000) < 300; lvl = res["S"][sel].max() - res["med"]
        csvw("t_comb", [base, k, fk, "%.1f" % lvl, "%.2f" % res["nd"]])
log("C done, resets %d" % NRST[0])
end = dt.datetime.now().replace(hour=23, minute=0, second=0)
for khz in [k for k in list(range(85000, 1625001, 200)) + list(range(2000000, 3125001, 200)) if reachable(k)]:
    if dt.datetime.now() > end: break
    res, r = point(khz); row("t_fine", khz, res, r)
log("FULLWB3 end at %d kHz, resets %d, sensors %s" % (khz, NRST[0], sensors()))

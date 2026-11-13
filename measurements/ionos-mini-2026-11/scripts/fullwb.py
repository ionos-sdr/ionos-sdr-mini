#!/usr/bin/env python3
# Full-coverage wideband run, no signal source (SMA open), 2026-11-10 night.
# Firmware: B<kHz> picks the LO divider (VCO ~5.2 GHz) from the per-divider channel entries;
# B<kHz>,<d> forces a divider. Per point: noise density, top-5 spurs, sample count.
#  A: 50-1700 MHz, 1 MHz steps     B: 1700-3300 MHz, 5 MHz steps
#  C: internal comb as a test signal: k x 19.5 MHz and k x 40 MHz, tuned +20 kHz -> tone at -20 kHz?
#  D: VCO range per divider: forced divider, VCO 3.4-7.2 GHz in 50 MHz steps (hang/no data = out of range)
#  E: fine 200 kHz map from 85 MHz upward until 06:55
import time, datetime as dt, numpy as np, serial
from soapyio import *
FS = 200000; N = 1 << 13
DIVS = [1,2,3,4,5,6,7,8,9,10,12,14,15,16,18,20,21,24]
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
NRST = [0]
def point(arg, cap=1.2):
    r = cmd("B%s" % arg, 1.0); time.sleep(0.5); z, _ = capture(cap)
    if len(z) < 4096:
        fg23_reset(); NRST[0] += 1; set_rate(FS); return None, r
    S = spectrum(z, N); Sd = 10 * np.log10(S + 1e-20); med = np.median(Sd)
    f = (np.arange(N) - N // 2) * FS / N; peaks = []
    for k in np.argsort(Sd)[::-1]:
        if abs(f[k]) < 400: continue
        if all(abs(f[k] - p[0]) > 1500 for p in peaks): peaks.append((f[k], Sd[k] - med))
        if len(peaks) >= 5: break
    dc = 20 * np.log10(abs(np.mean(z)) + 1e-12)
    return dict(n=len(z), nd=noise_dbfs_hz(S, FS, N), peaks=peaks, dc=dc, S=Sd, f=f, med=med), r
def row(tag, khz, d, res, r):
    if res is None: csvw(tag, [khz, d, "nodata", r.replace(",", ";")[:60]]); return
    csvw(tag, [khz, d, res["n"], "%.2f" % res["nd"], "%.1f" % res["dc"]] + ["%+.0f:%.1f" % p for p in res["peaks"]])
set_rate(FS); log("FULLWB start")
for khz in list(range(50000, 1700001, 1000)) + list(range(1705000, 3300001, 5000)):
    res, r = point(khz); row("fw_map", khz, 0, res, r)
log("A+B done, resets %d, sensors %s" % (NRST[0], sensors()))
for base, kmax in ((19500, 170), (39000, 85), (40000, 83)):
    for k in range(2, kmax + 1):
        fk = base * k
        if fk < 50000 or fk > 3300000: continue
        res, r = point(fk + 20)
        if res is None: csvw("fw_comb", [base, k, fk, "nodata"]); continue
        sel = np.abs(res["f"] + 20000) < 300; lvl = res["S"][sel].max() - res["med"] if sel.any() else float("nan")
        csvw("fw_comb", [base, k, fk, "%.1f" % lvl, "%.2f" % res["nd"]])
log("C done, resets %d" % NRST[0])
for d in DIVS:
    for vco in range(3400, 7201, 50):
        khz = int(vco * 1000 / (2 * d)); res, r = point("%d,%d" % (khz, d), cap=0.8)
        row("fw_vco", khz, "%d:%d" % (d, vco), res, r)
    log("D div %d done, resets %d" % (d, NRST[0]))
end = dt.datetime.now().replace(hour=6, minute=55, second=0)
if end < dt.datetime.now(): end += dt.timedelta(days=1)
khz = 85000
while dt.datetime.now() < end and khz <= 1600000:
    res, r = point(khz); row("fw_fine", khz, 0, res, r); khz += 200
log("FULLWB end at %d kHz, resets %d, sensors %s" % (khz, NRST[0], sensors()))

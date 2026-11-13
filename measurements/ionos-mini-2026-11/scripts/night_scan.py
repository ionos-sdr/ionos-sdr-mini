#!/usr/bin/env python3
# Overnight, no signal source: (1) self-generated spur / noise map 128.4-198.0 MHz in 200 kHz steps
# at R=2 (SPI 19.5 MHz) and R=8 (SPI 4 MHz) - which birdies are clock harmonics (k x 19.5 MHz),
# which follow the SPI clock; (2) then a SoapyIonos stream soak at 145 MHz / 200 ksps until 07:00.
import time, datetime as dt, numpy as np, serial
from soapyio import *
def B(khz): r = cmd("B%d" % khz, 1.0); time.sleep(0.4); return r
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
log("NIGHT-SCAN start")
for rate in (200000, 50000):
    set_rate(rate); N = 1 << 13 if rate == 200000 else 1 << 11
    for khz in range(128400, 198001, 200):
        B(khz); time.sleep(0.8); z, _ = capture(1.5)
        if len(z) < 4096: fg23_reset(); set_rate(rate); csvw("ns", [rate, khz, "nodata"]); continue
        S = spectrum(z, N); Sd = 10 * np.log10(S + 1e-20); med = np.median(Sd)
        f = (np.arange(N) - N // 2) * rate / N; k = int(np.argmax(np.where(np.abs(f) > 300, Sd, -999)))
        csvw("ns", [rate, khz, "%.2f" % noise_dbfs_hz(S, rate, N), "%+.0f" % f[k], "%.1f" % (Sd[k] - med)])
    log("scan fs=%d done, sensors %s" % (rate, sensors()))
B(0); cmd("F145000", 1.5); set_rate(200000)
end = dt.datetime.now().replace(hour=7, minute=0, second=0)
if end < dt.datetime.now(): end += dt.timedelta(days=1)
log("SOAK until %s" % end)
while dt.datetime.now() < end:
    z, _ = capture(60.0)
    csvw("nsoak", [len(z)] + list(sensors().values()))
    if len(z) < 100000: log("soak: short capture %d" % len(z))
log("NIGHT-SCAN end; sensors %s" % sensors())

#!/usr/bin/env python3
# Hypothesis: the broadband noise humps at 136.5/156/175.5/195 MHz are harmonics 7..10 of the
# FG23->ESP SPI clock (19.5 MHz at R<8, 4 MHz at R>=8). No signal source needed: compare the noise
# density at R=2 (200 ksps, SPI 19.5 MHz) and R=8 (50 ksps, SPI 4 MHz) on and around those points.
import time, numpy as np, serial
from soapyio import *
import soapyio
def B(khz): r = cmd("B%d" % khz, 1.0); time.sleep(0.4); return r
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
FREQS = [133.0, 136.0, 136.5, 137.0, 145.0, 152.0, 155.0, 155.5, 156.0, 156.5, 157.0, 175.0, 175.5, 176.0, 194.5, 195.0, 195.5]
log("SPI-SPUR start")
for rate in (200000, 50000, 200000):
    set_rate(rate)
    for fm in FREQS:
        B(int(round(fm * 1000))); time.sleep(1.2)
        z, _ = capture(2.0)
        if len(z) < 4096:
            fg23_reset(); set_rate(rate); csvw("spi", [rate, fm, "nodata"]); continue
        N = 1 << 13 if rate == 200000 else 1 << 11
        S = spectrum(z, N); Sd = 10 * np.log10(S + 1e-20)
        nd = noise_dbfs_hz(S, rate, N)
        csvw("spi", [rate, fm, "%.2f" % nd, "%.1f" % (Sd.max() - np.median(Sd))])
        log("fs=%d f=%.3f noise=%.2f dBFS/Hz peak/med=%.1f dB" % (rate, fm, nd, Sd.max() - np.median(Sd)))
log("SPI-SPUR end; sensors %s" % sensors())

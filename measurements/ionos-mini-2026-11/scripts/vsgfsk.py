#!/usr/bin/env python3
# Redo of vsgfull phase 3: the FSK reference demodulator expects 50 ksps (phase 3 ran at 200 ksps -> BER 0.375).
import os, time, numpy as np
from vsg60 import VSG
from soapyio import *
import fsk_lib
PAD = 30.0; ARB = os.path.abspath("fsk_prbs9_100k.binfc")
def B(khz): r = cmd("B%d" % khz, 1.0); time.sleep(0.4); return r
set_rate(50000); log("VSGFSK start (50 ksps)")
with VSG(port=5124) as v:
    try:
        okl, msg = v.load_arb(ARB, srate_hz=100000); log("arb load: %s %s" % (okl, msg)); v.on()
        for fm in (145, 434, 868, 1296, 2400, 3000):
            fh = fm * 1e6; B(int(fh // 1000)); v.freq(fh, verify=False); time.sleep(1.0)
            lo, hi = -140.0, -40.0; pts = []
            for _ in range(9):
                mid = (lo + hi) / 2; v.power(min(10.0, mid + PAD)); time.sleep(1.6)
                zz, _ = capture(1.5); e = fsk_lib.ber(zz, 50000)[0] if len(zz) > 20000 else 0.5; pts.append((mid, e))
                if e > 1e-2: lo = mid
                else: hi = mid
            csvw("v_fsk2", [fm, "%.1f" % hi] + ["%.1f:%.4f" % p for p in pts]); log("FSK %d MHz: %.1f dBm" % (fm, hi))
    finally:
        v.off(); v.modulation(True)
log("VSGFSK end; sensors %s" % sensors())

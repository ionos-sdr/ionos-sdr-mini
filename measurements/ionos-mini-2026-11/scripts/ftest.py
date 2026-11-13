import time, numpy as np
from soapyio import *
set_rate(200000); N = 1 << 14
def tone(cmdline):
    r = cmd(cmdline, 1.2); time.sleep(0.6); z, _ = capture(1.5)
    if len(z) < 4096: return None, r
    S = spectrum(z, N); f = (np.arange(N) - N // 2) * 200000 / N; Sd = 10*np.log10(S+1e-20)
    sel = np.abs(f + 20000) < 5000; k = np.argmax(np.where(sel, Sd, -999))
    return (f[k], Sd[k] - np.median(Sd)), r
for fk in [117000, 468000, 936000, 1404000, 2457000]:
    a, ra = tone("B%d" % (fk + 20)); b, rb = tone("F%d" % (fk + 20))
    log("%d kHz comb: B -> %s | F -> %s | %s" % (fk, a, b, rb))
for fk in [1012000, 1800000, 3200000]:
    b, rb = tone("F%d" % fk); log("F%d -> %s %s" % (fk, b, rb))
log("sensors %s" % sensors())

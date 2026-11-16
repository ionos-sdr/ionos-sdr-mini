# Weekend run, part 2 (2026-11-15 evening): blocks D (two-tone IIP3) and G (noise skirt) with the fixes
# (float frequency axis - np.arange is int32 on Windows and overflowed beyond +-65.5 kHz at 200 ksps / 32k FFT;
# G carrier search +-3 kHz), then the F stability loop until Monday 07:00. Same definitions as weekend.py.
src = open("weekend.py", encoding="utf-8").read().split('log("WEEKEND start')[0]
exec(src)
log("WEEKEND2 start"); set_rate(FS)
t = np.arange(100000) / 100000.0
fsk_lib.write_binfc(ARB_2T, (0.5 * (np.exp(2j*np.pi*10e3*t) + np.exp(-2j*np.pi*10e3*t))).astype(np.complex64))
v = RVSG()
try:
    v.modulation(False)
    for name, fn in (("D", D), ("G", G), ("F", F)):
        block(name, fn, v)
finally:
    try: v.off(); v.modulation(True); v.close()
    except Exception: pass
    log("WEEKEND2 end; VSG off")

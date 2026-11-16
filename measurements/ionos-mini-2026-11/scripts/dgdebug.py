src = open("weekend.py", encoding="utf-8").read().split('log("WEEKEND start')[0]
exec(src)
t = np.arange(100000) / 100000.0
fsk_lib.write_binfc(ARB_2T, (0.5 * (np.exp(2j*np.pi*10e3*t) + np.exp(-2j*np.pi*10e3*t))).astype(np.complex64))
v = RVSG()
try:
    set_rate(FS); ok, msg = v.load_arb(ARB_2T, srate_hz=100000); log("arb %s %s" % (ok, msg)); v.on()
    fh = 145e6; B(int(fh // 1000)); v.freq(fh + 40e3); c = 40e3 + PPM * fh
    v.power(-20); time.sleep(1.6); r = spec(1.0)
    S, f, z = r
    log("len z %d S %d f %.0f..%.0f c %.0f" % (len(z), len(S), f.min(), f.max(), c))
    Sd = 10*np.log10(S+1e-20); idx = np.argsort(Sd)[::-1][:8]
    log("top bins: %s" % ["%.0f:%.1f" % (f[i], Sd[i]-np.median(Sd)) for i in idx])
    for off in (-30e3, -10e3, 10e3, 30e3):
        m = np.abs(f - (c + off)) <= 2e3; log("off %+.0f: %d bins" % (off, m.sum()))
finally:
    v.off(); v.modulation(True); v.close()

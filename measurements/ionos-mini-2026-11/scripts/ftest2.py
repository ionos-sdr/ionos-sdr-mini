import time, numpy as np, SoapySDR
from SoapySDR import SOAPY_SDR_RX
from soapyio import *
log("hw %s" % {k: v for k, v in dict(dev.getHardwareInfo()).items() if k.startswith("freq") or k == "fw_esp"})
set_rate(200000); N = 1 << 14
for hz in [468020000, 936020000, 1404020000, 2457020000, 1800000000]:
    try: dev.setFrequency(SOAPY_SDR_RX, 0, float(hz)); ok = "set"
    except Exception as e: ok = "ERR %s" % e
    time.sleep(1.8); z, _ = capture(1.5)
    if len(z) < 4096: log("%d: no data (%s)" % (hz, ok)); continue
    S = spectrum(z, N); f = (np.arange(N) - N // 2) * 200000 / N; Sd = 10*np.log10(S+1e-20)
    sel = np.abs(f + 20000) < 6000; k = np.argmax(np.where(sel, Sd, -999))
    log("%d: %s, tone at %+.0f Hz, %.1f dB" % (hz, ok, f[k], Sd[k] - np.median(Sd)))
log("sensors %s" % sensors())

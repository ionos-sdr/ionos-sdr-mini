import time, numpy as np, serial
from soapyio import *
def fg23_reset():
    c = serial.Serial(); c.port = "COM4"; c.baudrate = 115200; c.timeout = 0.2; c.dtr = False; c.rts = False
    c.open(); c.write(b"FGRST\n"); time.sleep(1.5); c.write(b"FGINFO\n"); time.sleep(1.5); c.close(); time.sleep(5.0)
set_rate(200000)
for khz in [145000, 100000, 300000, 433000, 600000, 868000, 915000, 1200000, 1575000, 2400000]:
    r = cmd("B%d" % khz, 1.2); time.sleep(0.6); z, _ = capture(1.5)
    if len(z) < 4096:
        log("B%d: NO DATA (%s)" % (khz, r)); fg23_reset(); set_rate(200000); continue
    N = 1 << 13; S = spectrum(z, N); Sd = 10*np.log10(S+1e-20)
    log("B%d: n=%d noise=%.2f dBFS/Hz peak/med=%.1f | %s" % (khz, len(z), noise_dbfs_hz(S,200000,N), Sd.max()-np.median(Sd), r))
log("sensors %s" % sensors())

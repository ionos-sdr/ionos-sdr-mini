"""vsg_per.py — AIS packet error rate vs level: VSG60 plays ais_gen.py bursts,
the ionos-mini console (CH343 COM port) is counted per level step.

  usage: vsg_per.py wave.npy --port COM18 --levels -60,-65,-70 --step 20
                    [--atten 40] [--freq 161975000] [--tag HW|IQ] [--cmd "AISHW1"]
  counts console lines 'AIS RX:' (I/Q path) or 'AIS RX[HW]:' (on-chip path).
"""
import ctypes, os, sys, time, argparse, threading, re
import numpy as np, serial

ap = argparse.ArgumentParser()
ap.add_argument('wave'); ap.add_argument('--port', default='COM18')
ap.add_argument('--levels', default='-60,-70,-80'); ap.add_argument('--step', type=float, default=20)
ap.add_argument('--atten', type=float, default=40.0); ap.add_argument('--freq', type=float, default=161975000)
ap.add_argument('--fs', type=float, default=960000); ap.add_argument('--tag', default='')
ap.add_argument('--burst_per_s', type=float, default=10.0)
a = ap.parse_args()

os.add_dll_directory(r'C:\Program Files\Signal Hound\VSG')
v = ctypes.CDLL(r'C:\Program Files\Signal Hound\VSG\vsg_api.dll')
v.vsgGetErrorString.restype = ctypes.c_char_p
def chk(st, what):
    if st < 0: raise SystemExit('%s: %s' % (what, v.vsgGetErrorString(st)))
    if st > 0: print('warn', what, v.vsgGetErrorString(st))

h = ctypes.c_int(-1)
chk(v.vsgOpenDevice(ctypes.byref(h)), 'open'); h = h.value
chk(v.vsgSetFrequency(h, ctypes.c_double(a.freq)), 'freq')
chk(v.vsgSetSampleRate(h, ctypes.c_double(a.fs)), 'rate')
w = np.load(a.wave).astype(np.complex64)
iq = np.empty(2 * len(w), np.float32); iq[0::2] = w.real; iq[1::2] = w.imag
iqp = iq.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

# console counter
cnt = {'iq': 0, 'hw': 0}; lines = []; stop = False
s = serial.Serial(); s.port = a.port; s.baudrate = 115200; s.timeout = 0.2; s.dtr = False; s.rts = False; s.open()
def reader():
    buf = b''
    while not stop:
        buf += s.read(max(1, s.in_waiting))
        *ls, buf = buf.split(b'\n')
        for l in ls:
            t = l.decode('utf-8', 'replace')
            if 'AIS RX[HW]:' in t: cnt['hw'] += 1; lines.append(t.strip())
            elif 'AIS RX:' in t and 'type' in t: cnt['iq'] += 1; lines.append(t.strip())
th = threading.Thread(target=reader, daemon=True); th.start()

print('# %s VSG %.0f Hz, %d samples looped, %g bursts/s, attenuator %.1f dB' %
      (a.tag, a.freq, len(w), a.burst_per_s, a.atten))
print('#  VSG dBm  board dBm   sent  IQ ok  HW ok   IQ PER  HW PER')
res = []
try:
    for L in [float(x) for x in a.levels.split(',')]:
        chk(v.vsgSetLevel(h, ctypes.c_double(L)), 'level')
        chk(v.vsgRepeatWaveform(h, iqp, len(w)), 'repeat')
        time.sleep(1.0)                                  # settle, not counted
        c0 = dict(cnt); t0 = time.time()
        time.sleep(a.step)
        dt = time.time() - t0
        sent = a.burst_per_s * dt
        diq = cnt['iq'] - c0['iq']; dhw = cnt['hw'] - c0['hw']
        print('  %7.1f  %8.1f  %5.0f  %5d  %5d   %5.1f%%  %5.1f%%' %
              (L, L - a.atten, sent, diq, dhw, 100 * (1 - diq / sent), 100 * (1 - dhw / sent)), flush=True)
        res.append((L, L - a.atten, sent, diq, dhw))
        v.vsgAbort(h)
finally:
    v.vsgAbort(h); v.vsgCloseDevice(h)
    stop = True; time.sleep(0.3); s.close()
print('# last lines:'); [print('  ' + l[:110]) for l in lines[-3:]]

"""hw_sess.py — VSG plays a wave (or off) while console commands run on a
timeline; the whole console is logged.

  hw_sess.py --port COM18 --wave ais4r.npy --level -60 --freq 161972850
             --dur 40 --log out.txt "0:AISDBG" "1:AISHW1" "15:AISHWR" ...
  level 'off' = VSG not used.
"""
import ctypes, os, sys, time, argparse, threading
import numpy as np, serial

ap = argparse.ArgumentParser()
ap.add_argument('cmds', nargs='*'); ap.add_argument('--port', default='COM18')
ap.add_argument('--wave', default=''); ap.add_argument('--level', default='off')
ap.add_argument('--freq', type=float, default=161972850); ap.add_argument('--fs', type=float, default=960000)
ap.add_argument('--dur', type=float, default=30); ap.add_argument('--log', default='hw_sess.txt')
a = ap.parse_args()

v = None
if a.level != 'off':
    os.add_dll_directory(r'C:\Program Files\Signal Hound\VSG')
    v = ctypes.CDLL(r'C:\Program Files\Signal Hound\VSG\vsg_api.dll')
    h = ctypes.c_int(-1)
    assert v.vsgOpenDevice(ctypes.byref(h)) >= 0; h = h.value
    v.vsgSetFrequency(h, ctypes.c_double(a.freq)); v.vsgSetSampleRate(h, ctypes.c_double(a.fs))
    w = np.load(a.wave).astype(np.complex64)
    iq = np.empty(2 * len(w), np.float32); iq[0::2] = w.real; iq[1::2] = w.imag
    v.vsgSetLevel(h, ctypes.c_double(float(a.level)))
    v.vsgRepeatWaveform(h, iq.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(w))

s = serial.Serial(); s.port = a.port; s.baudrate = 115200; s.timeout = 0.1; s.dtr = False; s.rts = False; s.open()
out = open(a.log, 'w', encoding='utf-8'); stop = False
def reader():
    buf = b''
    while not stop:
        buf += s.read(max(1, s.in_waiting))
        *ls, buf = buf.split(b'\n')
        for l in ls: out.write('%.2f %s\n' % (time.time() - t0, l.decode('utf-8', 'replace').rstrip()))
t0 = time.time()
th = threading.Thread(target=reader, daemon=True); th.start()
todo = sorted((float(c.split(':', 1)[0]), c.split(':', 1)[1]) for c in a.cmds)
try:
    for t, c in todo:
        while time.time() - t0 < t: time.sleep(0.05)
        s.write((c + '\n').encode()); out.write('%.2f >>> %s\n' % (time.time() - t0, c))
    while time.time() - t0 < a.dur: time.sleep(0.1)
finally:
    stop = True; time.sleep(0.3); s.close(); out.close()
    if v: v.vsgAbort(h); v.vsgCloseDevice(h)
print('logged', a.log)

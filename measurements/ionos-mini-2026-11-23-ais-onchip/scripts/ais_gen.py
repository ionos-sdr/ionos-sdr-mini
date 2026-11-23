"""ais_gen.py — AIS GMSK burst generator (real NMEA payloads -> on-air I/Q).

    Copyright (c) 2026 Zoltan Doczi HA7DCD — MIT

  payload (6-bit armour) -> message bits -> bytes (first message bit = MSB,
  transmitted LSB first) + FCS (CRC-16/X.25, low byte first) -> bit stuffing
  -> ramp/training 24 x 0101.. -> flag -> data -> flag -> NRZI -> GMSK BT 0.4,
  h 0.5, 9600 bd. Several frames in one waveform, one burst per slot.

  usage: ais_gen.py out.npy [--fs 960000] [--slot_ms 100] [--foff 0]
"""
import sys, argparse, numpy as np

NMEA = [  # real Danube traffic, 2026-11-22/23 (ais_web log)
    "ENjMWT@HsKJGL?SP00000000000@chI>=`ON000001mRP0",       # type 21, 992438161 1664.8_G
    "ENjMWG@HsHtgSP0000000000000@cCkt=Qwm000001o2P0",       # type 21, 992438109
    "ENjMWE0HsILgSP0000000000000@cJSP=SOQ800001h2P0",       # type 21, 992438100 1629_G
    "ENjMWH0HsHsGK?a?S6000000000@cC2M=Q`1h00001i2L0",       # type 21, 992438112
]
BAUD = 9600

def armor2bits(p):
    s = []
    for c in p:
        v = ord(c) - 48
        if v > 40: v -= 8
        s += [(v >> (5 - k)) & 1 for k in range(6)]
    return s

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8): crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF

def frame_bits(nmea_payload, nbits=None):
    m = armor2bits(nmea_payload)
    if nbits: m = m[:nbits]
    m += [0] * ((-len(m)) % 8)
    by = bytes(int(''.join(map(str, m[k:k + 8])), 2) for k in range(0, len(m), 8))
    fcs = crc16(by)
    by += bytes([fcs & 0xFF, fcs >> 8])
    # transmitted LSB first per byte
    raw = [(b >> k) & 1 for b in by for k in range(8)]
    st, ones = [], 0
    for b in raw:
        st.append(b)
        ones = ones + 1 if b else 0
        if ones == 5: st.append(0); ones = 0
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    train = [0, 1] * 12
    # ITU-R M.1371: 8-bit ramp-up BEFORE the 24-bit training sequence (the
    # power ramp must not eat the training: the FG23 needs it for timing)
    rampup = [0, 1] * 4
    bits = rampup + train + flag + st + flag + [0, 1, 0, 1]  # a few bits of tail
    # NRZI: 0 -> transition, 1 -> no transition
    line, lv = [], 0
    for b in bits:
        if b == 0: lv ^= 1
        line.append(lv)
    return np.array(line, np.int8), by

def gmsk(line, fs, bt=0.4):
    sps = fs / BAUD
    n = int(len(line) * sps)
    t = np.arange(n) / fs
    sym = line[np.minimum((t * BAUD).astype(int), len(line) - 1)] * 2.0 - 1.0
    # Gaussian filter on the frequency pulse
    span = 4
    tt = np.arange(-span * sps, span * sps + 1) / sps
    sig = np.sqrt(np.log(2)) / (2 * np.pi * bt)
    g = np.exp(-tt ** 2 / (2 * sig ** 2)); g /= g.sum()
    f = np.convolve(sym, g, 'same') * (BAUD / 4)            # h 0.5 -> dev = baud/4 = 2400 Hz
    ph = 2 * np.pi * np.cumsum(f) / fs
    return np.exp(1j * ph).astype(np.complex64)

def ramp(x, fs, ms=0.8):
    n = int(fs * ms / 1000)
    w = np.ones(len(x), np.float32)
    w[:n] = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
    w[-n:] = w[:n][::-1]
    return x * w

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--fs', type=float, default=960000)
    ap.add_argument('--slot_ms', type=float, default=100); ap.add_argument('--foff', type=float, default=0)
    a = ap.parse_args()
    slot = int(a.fs * a.slot_ms / 1000)
    wave = []
    for p in NMEA:
        line, by = frame_bits(p, 168 if len(armor2bits(p)) < 200 else 272)
        b = ramp(gmsk(line, a.fs), a.fs)
        z = np.zeros(slot, np.complex64); off = int(a.fs * 0.01)
        z[off:off + len(b)] = b
        wave.append(z)
    w = np.concatenate(wave)
    if a.foff:
        w *= np.exp(2j * np.pi * a.foff * np.arange(len(w)) / a.fs).astype(np.complex64)
    np.save(a.out, w)
    print('frames %d, %d samples (%.2f s) at %.0f sps, burst %.1f ms' %
          (len(NMEA), len(w), len(w) / a.fs, a.fs, len(b) / a.fs * 1000))

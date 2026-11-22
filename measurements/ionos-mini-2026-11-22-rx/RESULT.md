# Receive tests — APRS, AIS, ground loop, TFT waterfall (22 Nov 2026)

Board: ionos-mini rev-B3 2L + BRD4265B (434 MHz match), ESP MAC 28:84:85:b8:1a:14.
Firmware: `ionos-sdr` branch `board/ionos-mini-idf` (`9a082af` APRS channel FIR, `04a2b24` AIS
mode, `f2106ca` TFT waterfall). Location: Budapest, home, ~1 km from the Danube. Antenna: mag-mount
2 m whip, clamped to a radiator as counterpoise. Captures: SpyServer over WiFi, 50 ksps int16
(36–480 MB each, not in git; the decoded results are).

## 1. APRS 144.800 — channel filter before the discriminator

The firmware fed the FM discriminator through a 2-sample boxcar, so the whole ±12.5 kHz band
reached the delay-multiply AFSK demodulator. A decimating complex FIR (Q15, 23 taps at 50 ksps,
4.5 kHz) replaced it. Measured with the bit-exact PC port of the firmware chain (`tools/fwport.c`
in `ionos-sdr`) on a real 20-min capture with 14 bursts at 11–15 dB over the 50 kHz floor:

| Variant | Packets |
|---|---|
| old boxcar | 0 |
| old boxcar, PHASE_NUDGE 2 / 3 / 4, float atan2, double resampler | 0 |
| **FIR 23 taps, 4.5 kHz** | **20** (every burst) |
| FIR 23 taps, 4 / 5 / 6 / 7 kHz | 21 / 21 / 20 / 13 |
| FIR 63 taps, 6 kHz | 18 |
| capture shifted ±1.05 kHz, FIR 4.5 kHz | 20 / 20 |
| independent float reference (`refdemod.py`) | 12 |

Live, the same day: ~25 packets/h gated to APRS-IS between 13:00 and 15:00 (the old firmware:
1 packet in a day at the office).

## 2. AIS 161.975 (channel A)

| Condition | Duration | Bursts | With a ≥1 ms gain dip | Decoded (port = reference) |
|---|---|---|---|---|
| USB from a mains-charged laptop, antenna on radiator | 720 s | 398 | 386 | 13 = 13 |
| same, on-device FFT off (`F0`) | 90 s | 45 | 44 | 1 |
| same, FFT on (`F1`) | 90 s | 52 | 50 | 1 |
| **powerbank**, antenna on radiator | 90 s | 63 | 1 | **56** |
| powerbank, live guest map (70 min) | 4245 s | – | – | 788 NMEA, 82 stations |
| USB from laptop, antenna off radiator | 90 s | 0 | – | 0 |

Live message mix (70 min): type 21 AtoN 567 (virtual river-km buoys, e.g. "1645.3_G"), type 4
shore station 101, types 20/23 59, types 1–3 55, type 8 4, junk 2 (types 40/48, CRC by chance).

Synthetic GMSK sweep (20 bursts/point, ±500 Hz, SNR in 14 kHz), float reference:

| Channel LPF | Post filter | 15 dB | 12 dB | 10 dB |
|---|---|---|---|---|
| 5 kHz | none | 19 | 11 | 2 |
| **6 kHz** | **none** | **20** | **17** | **9** |
| 8 kHz | none | 14 | 0 | 0 |
| 6 kHz | Gaussian BT 0.5 | 19 | 12 | 4 |

Bit order (real traffic decides, CRC cannot): the HDLC bytes assembled first-bit-to-LSB are the
message bytes MSB-first; the per-byte reversed variant is CRC-correct nonsense.

Per-packet RF parameters (powerbank run, 56 packets): level −46 … −36 dBFS, SNR 9–25 dB
(median 15 dB), carrier offset within ±600 Hz.

## 3. Ground loop: 12–17 dB gain dips every 20 ms

On the mains-charged laptop's USB, with the antenna clamped to a radiator in a house without
protective earth, the receiver gain drops 12–17 dB for 2–4 ms (median 2.7 ms) every ~20 ms.

- Noise-only power is modulated at 50/100/150 Hz: the 100 Hz line is +45.6 dB over the median on
  mains USB, +13.3 dB on the powerbank.
- On a CW carrier (Morfeus, 144.800) the carrier stays inside the dip at −12 dB with continuous
  phase (|Δφ| ≤ 0.06 rad): no sample loss.
- Dip start positions modulo the 256-sample SPI block are uniform: not the data path.
- Not the on-device display FFT (20 ms period): `F0` changes nothing.
- It killed APRS too after dark (0–2 packets/h); powerbank cures it.

Rule for field and home tests: power the board from a battery (or isolate the USB) when the
antenna touches a building ground.

## 4. TFT waterfall (on-device display)

A line-by-line PC emulator of `iq_fft.cpp` + `tft.cpp` (`tools/tftemu.py` in `ionos-sdr`) on
the captures above showed why the waterfall looked mushy:

- a row was drawn from only the last of every 3 FFTs (61 ms), so a 26 ms AIS burst was faint or missing;
- 40 dB range and −2 dB lift left the noise mid-blue;
- the DC patch interpolated ±8 bins (±390 Hz) and erased the centre of on-channel APRS signals
  and test carriers.

Now: per-bin peak of the 3 FFTs, 24 dB range, +4 dB lift, gamma 0.7, alpha 0.6, DC patch ±1 bin
(all runtime-settable: `Fset rowmax= gamma= dcw= range= lift=`).

A ~+17–19 kHz drifting "hook" on the waterfall, restarting every few seconds, follows the tuning
(seen at 144.8 and 162 MHz) and is 20× more frequent on the mains USB than on the powerbank:
conducted interference from the laptop charger, not an RF signal.

## Files

- `nmea_powerbank_90s.txt` — the 56 AIS sentences of the powerbank run
- `holes.py`, `holes2.py` — burst / gain-dip statistics from a capture

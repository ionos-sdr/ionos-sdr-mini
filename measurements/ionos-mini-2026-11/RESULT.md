# ionos-sdr-mini, November 2026 — measurement campaign

Board: ionos-sdr-mini rev-B3 2L + Silicon Labs BRD4265B (EFR32FG23, **434 MHz match**), ESP32-S3, 16-bit I/Q over USB (TinyUSB CDC).
Firmware: [`ionos-sdr/ionos-sdr`](https://github.com/ionos-sdr/ionos-sdr), branch `board/ionos-mini-idf`. Host: [SoapyIonos](https://github.com/ionos-sdr/SoapyIonos).
Full report for 2–9 Nov: [`docs/ionos-mini-measurements-2026-11.md`](../../docs/ionos-mini-measurements-2026-11.md) · charts: [`charts/`](charts/).

**Time on test so far: ≈ 119 h** (2–13 Nov 2026, snapshot 13 Nov 09:00; the weekend run continues until 16 Nov 07:00)

| Category | Hours |
|---|---|
| RF with a signal generator (VSG60) | ≈ 68 |
| RF without a signal source (self-noise, residual spurs, coverage) | ≈ 19 |
| USB-only soaks | ≈ 32 |

## Timeline

| Period (local time) | Measurement | Hours | Data |
|---|---|---|---|
| 11-02 … 11-06 | USB soaks, HWCDC 50 ksps → TinyUSB 200 ksps, 256 kB / 2 MB ring, WiFi on/off | 32.4 | `data/usb-soak/` |
| 11-06 17:42 → 11-08 17:50 | 145 MHz RF characterisation, 146 cycles (gain, linearity, NF, passband, image, drift) | 48.1 | `data/rf-145MHz-48h/` |
| 11-08 18:04 → 23:06 | wideband sweep with the 145 MHz PHY divider (map, CW, FSK) via SoapyIonos | 5.0 | `data/wideband/` |
| 11-08 23:49, 11-09 09:01 | re-check: noise with VSG off, ±6.25 kHz sidebands, FSK outliers | 0.4 | `data/wideband/sp_rc_*` |
| 11-09 23:38 → 23:55 | self-noise: SPI-clock test (19.5 vs 4 MHz), 128–198 MHz spur scan | 0.3 | `data/self-noise-2026-11-09/` |
| 11-09 23:58 → 11-10 06:55 | **full coverage, SMA open** (20 dB pad + open coax): 50 MHz–3.3 GHz map, on-board comb, VCO window per LO divider, 200 kHz fine map | 6.9 | `data/fullcoverage-open-2026-11-10/` |
| 11-10 09:27 → 20:55 | **full coverage, terminated** (30 dB pad + 50 Ω): noise floor, residual spurs, comb, 200 kHz fine map 85–1625 / 2000–3125 MHz | 11.5 | `data/fullcoverage-terminated-2026-11-10/` |
| 11-12 14:16 → 18:19 | **VSG, full coverage**: gain/NF/MDS 5 MHz grid 97–3100 MHz, 1 MHz grid 97–1562 MHz, linearity, FSK | 4.1 | `data/vsg-fullcoverage-2026-11-12/` |
| 11-12 22:43 → (16 Nov 07:00) | **weekend run**: gain/NF 1 MHz 2025–3100 MHz, linearity at 21 frequencies, FSK every 25 MHz + BER curves, spurious responses 30 MHz–6 GHz, stability loop | 10.1 so far | `data/weekend-2026-11-12/` |

## Measurement types

| # | Type | Where | Chart |
|---|---|---|---|
| 1 | USB throughput and long soaks (lost/truncated blocks, ring size, host stalls) | usb-soak | – |
| 2 | Gain, linearity, ADC clip point | rf-145MHz-48h, vsg, weekend (B) | 08, 23, 27 |
| 3 | Noise figure and MDS (10 dB SNR / 500 Hz) | rf-145MHz-48h, wideband, vsg, weekend (A) | 02, 03, 21, 22, 24 |
| 4 | Passband shape and image rejection at 50/100/200 ksps | rf-145MHz-48h | 09 |
| 5 | Frequency accuracy and drift (crystal, diurnal, weekend) | rf-145MHz-48h, weekend (F) | 05, 07, 29 |
| 6 | Tuning range: LO divider / VCO window per divider, coverage map | wideband, fullcoverage-open | 01, 10, 14 |
| 7 | Lock proof with the on-board clock comb (k × 39 / 19.5 / 40 MHz) | fullcoverage-open/-terminated | 10, 17 |
| 8 | Noise floor and residual (self-generated) spurs, open vs terminated input | self-noise, fullcoverage-* | 11, 12, 13, 15, 16 |
| 9 | 2-FSK 5 kbps sensitivity (BER 10⁻²) vs frequency, full BER curves | wideband, vsg, weekend (C) | 06, 25, 26 |
| 10 | Spurious responses (RX fixed at 145/434/868 MHz, VSG 30 MHz–6 GHz) | weekend (E) | 28 |
| 11 | Long-term gain / NF / frequency stability at 12 frequencies | weekend (F) | 29 |
| 12 | SoapyIonos driver soak (all VSG runs go through the driver) | every `*_stdout.log.gz` | – |

Still to do: two-tone IIP3 and phase noise / reciprocal mixing (weekend blocks D and G failed and are re-run on 15 Nov), TX output vs frequency (needs the BB60C).

## Key results

| | |
|---|---|
| USB, 200 ksps 16-bit I/Q (813 kB/s), 40 h | 86 M blocks, 0 device drops, 0.65 ppm host-side loss |
| Coverage (receives an external signal) | **97 – 1562 MHz and 2025 – 3100 MHz**; no LO divider for ~1625–2000 MHz |
| 434 MHz (matched) | gain 63 dB, **NF 3–4 dB**, MDS −133 dBm, FSK −115 dBm, clip −62 dBm |
| 145 MHz | gain 53 dB, NF 8–9 dB, MDS −128 dBm, FSK −110 dBm, clip −53 dBm |
| 868 MHz | gain 35 dB, NF ≈ 23 dB, MDS −114 dBm, FSK −93 dBm, clip −32 dBm |
| 1296 MHz | gain 16 dB, NF ≈ 40 dB, FSK −73 dBm, no clip up to −20 dBm |
| 2400 / 3000 MHz | gain ≈ 2 / 12 dB, NF ≈ 55 / 46 dB, FSK −55 / −59 dBm |
| Why it falls off above 600 MHz | the 434 MHz RX match (82 nH series L into the ~1.2 pF high-impedance LNA, TX LC low-pass on the same node) — the chip itself works to 3.1 GHz (comb) |
| Spurious responses @ 434 MHz | worst −70 dBc (11 × LO, 4775 MHz), all others ≤ −104 dBc; no image response found |
| Spurious responses @ 868 MHz | worst −81 dBc (1085 MHz), others ≤ −89 dBc |
| Residual spurs (terminated) | mainly k × 19.5 / 39 MHz (FG23 clocks) and k × 40 MHz (ESP crystal, below ~1.5 GHz) |
| Stability (4.5 h snapshot) | gain σ 0.02–0.03 dB below 1 GHz; crystal +4.9…+5.35 ppm (uncorrected) |
| Passband / image @ 200 ksps | 88 kHz at −3 dB (PHY channel filter), image ≥ 42 dB |

Caveats: P_in = VSG level − 30 dB pad; the long coax is **not** subtracted (matters above ~1 GHz). The 145 MHz spurious-response panel is dominated by the VSG60's own output spurs. "Open" runs had 20 dB pad + open coax on the input.

## Setup

VSG60 (SCPI port 5124) → long coax → 30 dB pad → BRD4265B SMA. Host: Windows, 4-deep USB hub chain, radioconda Python, SoapyIonos (`driver=ionos`). Tuning in the wide runs uses the FG23 `B<kHz>` command (no crystal correction): one channel entry per LO divider, divider chosen inside the measured VCO window.

## Scripts (`scripts/`)

| File | Purpose |
|---|---|
| `vsg60.py` | minimal VSG60 SCPI client, every set read back |
| `soapyio.py` | SoapySDR primitives (command, rate, capture, sensors, spectrum, noise density, CSV/log) |
| `longprog.py` | 48 h characterisation loop at 145 MHz |
| `wideband_soapy.py`, `wideband.py` | wideband map / edges / CW / FSK with the 145 MHz PHY divider |
| `recheck.py` | re-check of suspicious points |
| `spi_spur.py`, `night_scan.py` | self-noise: SPI-clock test, 128–198 MHz spur scan |
| `btest_div.py` | quick check of the per-divider `B` command |
| `fullwb.py`, `fullwb2.py` | full coverage, open input: map, comb, VCO window per divider, fine map |
| `fullwb3.py` | full coverage, terminated input |
| `ftest.py`, `ftest2.py` | `F` tuning (crystal correction) check through SoapyIonos |
| `vsgfull.py`, `vsgfsk.py` | VSG full-coverage gain/NF/MDS, linearity, FSK |
| `weekend.py` | weekend run (blocks A–G, self-healing VSG link) |
| `fsk_lib.py` | 2-FSK PRBS9 Arb generator, discriminator demod, BER |
| `soak_full.py`, `soak200.py`, `flood_exp*.py`, `passband.py`, `con4.py` | USB soaks, flood tests, passband, console |

COM ports are hard-coded for the test PC (console `COM4`). Arb files are generated by the scripts.

## Data (`data/`) and logs (`logs/`)

CSV columns are written by `csvw()` in each script (first column: timestamp; see the `csvw(...)` calls). Logs are the scripts' stdout, gzipped.

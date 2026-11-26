# AIS dual-channel I/Q vs FG23 on-chip, ID2 + VSG60A, 25-26 Nov 2026

Firmware 47d3ff8 (ionos-sdr `exp/fg23-ais-onchip`): FG23 at 162.000 MHz, 100 ksps; per channel a DDC
(NCO -/+25 kHz, 61-tap decimating FIR to 25 ksps) into its own `ais_rx` instance, FCS de-duplication,
noise floor held while a signal is present, MMSI/type plausibility filter. AFC toggled per cycle
(odd cycles `AISIQA8` = on, path `iq`; even cycles `AISIQA0` = off, path `iq_noafc`). On-chip (`hw`) every cycle.

Run: 2026-11-25 12:57 -> 2026-11-26 08:07, 34 cycles, 3196 points (`data/overnight3.csv`).
Cycles 11 and 19 are excluded: they coincide with two full firmware builds on the measurement PC
(18:37-19:00, 23:13-23:41); every path, on-chip included, failed at -96 dBm in those windows.
`data/overnight2.csv` is the first, short run (3 cycles) before the noise-floor-hold fix (slot stress 70 % PER).

| | on-chip | dual I/Q, AFC off | dual I/Q, AFC on | single I/Q (23 Nov) |
|---|---|---|---|---|
| 50 % point, channel A | -105.48 +/- 0.10 dBm | **-106.21 +/- 0.17 dBm** | -105.73 +/- 0.21 dBm | -106.19 +/- 0.18 dBm |
| PER -104 dBm: A / B alone | 14.3 / 14.9 % | 6.6 / 7.1 % | 13.5 / 8.8 % | 6.4 % / - |
| PER -104 dBm: A / B simultaneous | - | 8.3 / 8.1 % | 14.9 / 9.3 % | - |
| offset with PER <= 15 % at -103 dBm | -3 ... +3 kHz | 0 ... +1 kHz | **-4 ... +4 kHz** | 0 ... +1 kHz |
| slot stress (37.5/s) -104 dBm | 9.4 % | 6.0 % | 8.0 % | 6.4 % |
| CW limit at +/-25 kHz / +50 kHz | +50 / +50 dBc | +40 / +40 dBc | +40 / +40 dBc | +40 / < +30 dBc |

Two channels cost no sensitivity; AFC buys +/-4 kHz offset tolerance for 0.48 dB; the B->A alias of the
50 ksps plan is gone; near-channel blocking is still ~10 dB behind on-chip.
Report: `docs/reports/ionos-mini_AIS_report_EN_2026-11-26.pdf` / `..._jelentes_HU_2026-11-26.pdf` (section 6).

Scripts: `scripts/overnight_dual.py` (the run, VSG + console), `scripts/dual_charts.py` (charts).

#!/usr/bin/env python3
"""AIS measurement report, EN + HU (reportlab, DejaVu fonts).
usage: python scripts/report_build.py <pdf_out_dir> <chart_dir>   (charts from report_charts.py)"""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                Image, KeepTogether, PageBreak)

D = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DV', D + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', D + 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DVM', D + 'DejaVuSansMono.ttf'))
from reportlab.lib.fonts import addMapping
addMapping('DV', 0, 0, 'DV'); addMapping('DV', 1, 0, 'DVB'); addMapping('DV', 0, 1, 'DV'); addMapping('DV', 1, 1, 'DVB')

OUT = sys.argv[1]; IMG = sys.argv[2]
INK, MUTED, RULE, ACC = colors.HexColor('#2b2a26'), colors.HexColor('#6b6a63'), colors.HexColor('#d9d8d2'), colors.HexColor('#2a78d6')
ss = {
 'h0': ParagraphStyle('h0', fontName='DVB', fontSize=17, leading=21, textColor=INK, spaceAfter=2),
 'sub': ParagraphStyle('sub', fontName='DV', fontSize=9, leading=12, textColor=MUTED, spaceAfter=8),
 'h1': ParagraphStyle('h1', fontName='DVB', fontSize=12, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
 'h2': ParagraphStyle('h2', fontName='DVB', fontSize=9.5, leading=12, textColor=INK, spaceBefore=6, spaceAfter=2),
 'p': ParagraphStyle('p', fontName='DV', fontSize=8.6, leading=11.6, textColor=INK, spaceAfter=4),
 'b': ParagraphStyle('b', fontName='DV', fontSize=8.6, leading=11.6, textColor=INK, leftIndent=10, bulletIndent=2, spaceAfter=2),
 'cap': ParagraphStyle('cap', fontName='DV', fontSize=7.6, leading=9.6, textColor=MUTED, spaceAfter=6),
 'td': ParagraphStyle('td', fontName='DV', fontSize=7.8, leading=9.8, textColor=INK),
 'th': ParagraphStyle('th', fontName='DVB', fontSize=7.8, leading=9.8, textColor=INK),
 'key': ParagraphStyle('key', fontName='DV', fontSize=8.8, leading=12, textColor=INK, leftIndent=10, bulletIndent=0, spaceAfter=3),
}

def P(t, s='p'): return Paragraph(t, ss[s])
def B(t): return Paragraph(t, ss['b'], bulletText='•')
def K(t): return Paragraph(t, ss['key'], bulletText='▸')
def img(name, w, cap=None):
    from PIL import Image as PI
    im = PI.open(f'{IMG}/{name}'); h = w * im.height / im.width
    out = [Image(f'{IMG}/{name}', width=w, height=h)]
    if cap: out.append(P(cap, 'cap'))
    return KeepTogether(out)
def T(rows, widths, num_from=1):
    data = [[Paragraph(str(c), ss['th' if i == 0 else 'td']) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, INK), ('LINEBELOW', (0, 1), (-1, -1), 0.3, RULE),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 2.2),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2), ('LEFTPADDING', (0, 0), (-1, -1), 3),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 3)]))
    return t

W = A4[0] - 36 * mm

def footer(lang):
    def f(c, doc):
        c.saveState(); c.setFont('DV', 7); c.setFillColor(MUTED)
        c.drawString(18 * mm, 10 * mm, 'ionos-mini · AIS · rev. 2 · 2026-11-26' if lang == 'en' else 'ionos-mini · AIS · 2. kiadás · 2026. 11. 26.')
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page)); c.restoreState()
    return f

TX = {}
TX['en'] = dict(
 title='AIS reception on the ionos-mini: I/Q path vs FG23 on-chip demodulator',
 sub='Measurement report · instrument (VSG) and field tests · 22–26 Nov 2026 · HA7DCD · rev. 2: dual-channel I/Q (section 6)',
 s_sum='Summary',
 key=[
  '<b>Clean, on-frequency signal:</b> the I/Q path is 0.74 dB more sensitive. 50 % PER at <b>−106.19 dBm</b> (I/Q, sd 0.17) vs <b>−105.45 dBm</b> (on-chip, sd 0.10), 26 cycles over 13 h, no drift.',
  '<b>Frequency offset:</b> on-chip tolerates <b>±3 kHz</b> (PER ≤ 7.7 % at −103 dBm); the I/Q demod only <b>≈ ±1 kHz</b> (42 % at −1 kHz, 52 % at +2 kHz).',
  '<b>Blocking:</b> on-chip holds a CW at +50 dBc from ±25 to −300 kHz. The I/Q path fails at +50 dBc at ±25 kHz, and a carrier on <b>channel B blocks channel A at any level</b> (decimation alias in the 50 ksps stream).',
  '<b>Live traffic</b> (same antenna, 5 min / 5 min alternation, 14.7 h counted): on-chip <b>101 msg/h</b>, I/Q <b>81 msg/h</b> → <b>1.24×</b>. 74 stations heard by both, 20 by I/Q only (one message each, mostly −103…−106 dBm, incl. an invalid 10-digit MMSI), 1 by on-chip only.',
  '<b>Supply:</b> mains-charged laptop USB + antenna on building ground → 12–17 dB gain dips every 20 ms, 3 % of bursts decoded. Powerbank: 89 %.',
  '<b>Dual-channel I/Q (rev. 2, 25–26 Nov, 34 cycles / 19 h):</b> A and B decoded <b>at the same time</b> from one FG23 (162.000 MHz, 100 ksps). No sensitivity cost: 50 % point <b>−106.21 dBm</b> (AFC off, sd 0.17) = single-channel I/Q. B alone and A+B simultaneous track A within the scatter. With AFC on: <b>±4 kHz</b> offset tolerance (PER ≤ 15 % at −103 dBm, better than on-chip) for <b>0.48 dB</b> sensitivity (−105.73 dBm). The B→A alias is gone: a carrier on B now blocks A only at ≥ +50 dBc.',
  '<b>Verdict (rev. 2):</b> dual-channel I/Q with AFC is now the better receiver on paper: on-chip sensitivity (−105.7 vs −105.5 dBm), wider offset tolerance, two channels. On-chip keeps ~10 dB more blocking margin near the channel (+50 dBc vs +40 dBc at ±25 kHz). Next: live A/B comparison on ID1.'],
 s_setup='1  Setup',
 setup=[
  '<b>Hardware:</b> ionos-mini rev-B3 2L (ESP32-S3 + EFR32FG23 radio board BRD4265B, matched for 434 MHz — 162 MHz is outside the matched band, so read the absolute levels as relative; the comparison of the two paths is the result). ID2 (office, cabled to the VSG), ID1 (home, antenna).',
  '<b>I/Q path:</b> FG23 <font name="DVM">RX_IQDATA_FILTLSB</font>, 50 ksps at 161.985 MHz → SPI → ESP32 <font name="DVM">ais_rx.c</font>: NCO to channel A, complex FIR 6 kHz (Q15), FM discriminator, resample to 48 kHz, 5 parallel sample-phase lanes with NRZI/HDLC/CRC-16. Channel A only.',
  '<b>On-chip path:</b> FG23 AIS PHY (2GFSK 9600 Bd, <b>LEGACY</b> demod — the configurator default TRECS_VITERBI gave timing detect but no sync), 16-bit sync word 0x80CC/0x7F33 (LSB-first, measured from captures), <font name="DVM">ais_hw.c</font> on the FG23 does NRZI/HDLC/CRC and re-arms at the closing flag. Frames go to the ESP in AIS1 blocks. Channel A or B (one at a time).',
  '<b>Instrument:</b> Signal Hound VSG60A → 40 dB attenuator → board; levels are at the board. Waveform: 4 real type-21 frames, GMSK BT 0.4, 9600 Bd, ITU ramp + 24-bit training, 10 bursts/s, VSG at 161 972 850 Hz (compensates ID2 crystal ≈ +13.5 ppm). 200 bursts per point, settle 1.5 s excluded.'],
 s_hours='2  Test campaigns and hours',
 hours=[['Campaign', 'Board / place', 'Duration', 'Volume'],
  ['Field captures (I/Q, SpyServer)', 'ID1, home, 2 m mag-mount on radiator', '22 Nov: 720 s + 4 × 90 s', '558 bursts analysed (gain dips, decodes)'],
  ['Field live map', 'ID1, home (Danube ~1 km)', '22 Nov: 70 min', '788 NMEA, 82 stations'],
  ['VSG single sweeps', 'ID2, office, VSG60A', '23 Nov, until 18:13', 'full matrix once per path'],
  ['VSG overnight matrix', 'ID2, office, VSG60A', '23 Nov 18:53 → 24 Nov 07:57 (13.1 h)', '26 cycles, 2118 points, 479 700 bursts'],
  ['Live AISBENCH (alternating)', 'ID1, home, antenna', '23 Nov 17:21 → 24 Nov 12:28 (19.1 h)', '14.7 h logged by the proxy (7.36 h per path): 1339 msgs, 95 stations'],
  ['VSG overnight matrix, dual I/Q', 'ID2, office, VSG60A', '25 Nov 12:57 → 26 Nov 08:07 (19.2 h)', '34 cycles (2 excluded), 3196 points'],
  ['<b>Total</b>', '', '<b>32.3 h instrument (+ daytime sweeps), ≈ 20.5 h field</b>', '']],
 cap_tl='Instrument and field runs overlapped: ID2 on the VSG and ID1 on the antenna ran at the same time.',
 s_inst='3  Instrument tests (VSG60A, ID2)',
 h_sens='3.1  Sensitivity',
 sens='PER vs level, channel A, mean ± sd of 26 cycles. Channel B (on-chip only) tracks channel A within the scatter (−104 dBm: 13.4 ± 2.8 %, −106 dBm: 64.6 ± 3.3 %).',
 sens_t=[['dBm', '−100', '−102', '−103', '−104', '−105', '−106', '−107', '−108'],
         ['on-chip', '0', '0.4', '4.2', '14.1', '35.8', '66.8', '91.0', '99.2'],
         ['I/Q', '0', '0.3', '1.5', '6.4', '19.6', '44.5', '72.1', '91.6']],
 cap_sens='PER %, mean over 26 cycles. 50 % point: on-chip −105.45 dBm (range −105.62…−105.22), I/Q −106.19 dBm (−106.40…−105.75).',
 cap_p50='50 % point per cycle, interpolated. Both stable through the night; the I/Q scatter (sd 0.17 dB) is about twice the on-chip one (0.10 dB).',
 h_foff='3.2  Frequency offset',
 foff='At −103 dBm the on-chip path (PHY AFC, 3.24 kHz tolerance) stays ≤ 7.7 % from −3 to +3 kHz. The I/Q demod has no frequency tracking: it reaches 42 % at −1 kHz and ≥ 97 % beyond ±2…3 kHz. Real AIS transmitters are off by a few hundred Hz to ~1 kHz and the receiver crystal adds to that — this, not the 0.74 dB, decides live reception.',
 h_cw='3.3  Selectivity (CW interferer)',
 cw='Wanted signal −100 dBm on channel A, CW at the offset and level shown. The I/Q failure at +50 kHz is not a filter-skirt problem: channel B (+40 kHz from the 161.985 MHz I/Q centre) folds onto channel A in the 50 ksps stream. Real channel-B traffic does the same. At 60 dBc the wanted signal is −60 dBFS on the VSG; VSG noise/spurs may contribute — treat the 60 dBc column with care.',
 h_slot='3.4  Slot stress and channel B',
 slot='A burst in every slot (37.5/s): −96 dBm 0 % on both paths in all 26 cycles; −104 dBm on-chip 9.4 ± 1.2 %, I/Q 6.4 ± 1.1 % (same ranking as single bursts). The on-chip re-arm after the closing flag catches the next slot.',
 h_df='3.5  Reported frequency offset',
 df='I/Q Δf drifted +295 → +224 Hz overnight (ID2 crystal with the office temperature). The on-chip Δf (RAIL estimate) is not calibrated yet (≈255 Hz steps, wrong scale) — use only as a relative indicator.',
 s_field='4  Field tests (ID1, home, Danube ~1 km)',
 h_gl='4.1  Supply ground loop (22 Nov)',
 gl='Laptop on mains charger, antenna clamped to a radiator in a house without protective earth: receiver gain drops 12–17 dB for 2–4 ms every ~20 ms (100 Hz line +45.6 dB over the median noise; on powerbank +13.3 dB). Carrier phase stays continuous through the dip (no sample loss); dip positions are uniform vs the SPI block (not the data path). Rule: battery or isolated USB whenever the antenna touches building ground.',
 h_live='4.2  Live comparison, AISBENCH (23–24 Nov)',
 live='Five minutes I/Q, five minutes on-chip, same antenna, 19 h. Counted by the proxy over 14.7 h (7.36 h each): I/Q 597 messages = 81/h, on-chip 742 = 101/h, <b>ratio 1.24</b>. The receiver-side tally to 08:02 agrees (721 vs 902, 88 slots each, 1.25). On-chip wins in 10 of 13 full hours.',
 cap_st='Per station, live. Dotted line: equal count. Most points sit above it (on-chip more). The 20 I/Q-only stations each have exactly one message at −103…−106 dBm reported level; one MMSI has 10 digits (invalid) → part of them are CRC-by-chance decodes, not weak real stations.',
 mix='Message mix, 22 Nov live map (70 min, 788 sentences): type 21 AtoN 567 (virtual river-km buoys), type 4 base station 101, types 20/23 59, types 1–3 55, type 8 4, junk 2 (types 40/48).',
 s_b='5  Can channel B run on the I/Q path at the same time? (written 25 Nov; done since, see section 6)',
 b=[
  '<b>On-chip A + I/Q B at once: no.</b> The FG23 has one receiver; it is either streaming I/Q or running the AIS PHY. Native A+B needs two radios (or hopping, which loses messages on the idle channel).',
  '<b>I/Q A + I/Q B: yes, with a different tuning plan — not implemented or measured yet.</b>',
  'Today: centre 161.985 MHz, 50 ksps → A at −10 kHz, B at +40 kHz, outside ±25 kHz, aliasing onto −10 kHz = channel A. That is the measured “carrier on B blocks A” result.',
  'Plan: centre <b>162.000 MHz, 100 ksps</b> → A at −25 kHz, B at +25 kHz, both inside ±50 kHz, ~18 kHz guard to the band edge. <font name="DVM">ais_rx.c</font> is already one channel per instance with its own NCO and accepts 25–200 ksps → two instances at −25 / +25 kHz, unchanged code.',
  'Transport: FG23 → ESP at 100/200 ksps is proven (200 ksps, 9.1 h soak, FG23 LOST 0).',
  'ESP load: the per-sample part (NCO + 6 kHz complex FIR) runs at 2× rate for 2 channels ≈ 4× today; the 48 kHz part (discriminator, 5 lanes, HDLC) 2×. Not profiled yet — must be measured with the TFT waterfall and WiFi running.',
  'Side effects: the B→A alias disappears; the ±25 kHz adjacent case becomes a real adjacent-channel case set by the 6 kHz FIR and the FG23 decimation at 100 ksps — re-measure with the same CW matrix.',
  '<b>Recommendation:</b> (1) dual-channel I/Q at 162.000 MHz / 100 ksps, (2) frequency tracking in <font name="DVM">ais_rx.c</font> (offset estimate from the 24-bit training, or per-board crystal correction in NVS) — this recovers the 1.24× live deficit, (3) rerun the overnight matrix on A and B incl. CW at ±25/±50/±100 kHz and profile the ESP. If I/Q then matches on-chip on offset tolerance, it is the better receiver: +0.74 dB and two channels from one FG23.'],
 s_dual='6  Dual-channel I/Q: measured (rev. 2, 25–26 Nov)',
 dual=[
  '<b>Implementation</b> (firmware 47d3ff8, ID2): FG23 at 162.000 MHz, 100 ksps (R = 4 from 400 kHz). Per channel a DDC (NCO ∓25 kHz + 61-tap decimating FIR to 25 ksps) feeds its own <font name="DVM">ais_rx</font> instance; duplicate frames are dropped by FCS. AFC: carrier-offset tracker per channel (AISIQA8 on / AISIQA0 off). Noise floor held while a signal is present (fixes the slot-stress failure of the first run: 70 % → 6 % PER). MMSI/type plausibility filter on. ESP load ≈ 35 % of one core.',
  '<b>Run:</b> VSG60A → 40 dB → ID2, same waveforms and levels as the 23 Nov matrix plus channel B alone (E) and A+B simultaneous (F, two bursts in the same slot, ±25 kHz). Odd cycles AFC on, even cycles AFC off; the on-chip path in every cycle as the reference. 34 cycles in 19.2 h. <b>Cycles 11 and 19 excluded:</b> they coincide exactly with two full firmware builds on the measurement PC (18:37–19:00, 23:13–23:41) — every path, including on-chip at −96 dBm, failed in those windows (host starvation, not radio).'],
 dual_t=[['', 'on-chip', 'dual I/Q, AFC off', 'dual I/Q, AFC on', 'single I/Q (23 Nov)'],
  ['50 % point (dBm)', '−105.48 ± 0.10', '<b>−106.21 ± 0.17</b>', '−105.73 ± 0.21', '−106.19 ± 0.18'],
  ['PER −104 dBm, A', '14.3 %', '6.6 %', '13.5 %', '6.4 %'],
  ['PER −104 dBm, B alone', '14.9 %', '7.1 %', '8.8 %', '—'],
  ['PER −104 dBm, A / B simultaneous', '—', '8.3 / 8.1 %', '14.9 / 9.3 %', '—'],
  ['PER −106 dBm, A / B simultaneous', '—', '46.3 / 50.8 %', '58.8 / 50.7 %', '—'],
  ['Offset, PER ≤ 15 % at −103 dBm', '−3 … +3 kHz', '0 … +1 kHz', '<b>−4 … +4 kHz</b>', '0 … +1 kHz'],
  ['Slot stress −104 dBm', '9.4 %', '6.0 %', '8.0 %', '6.4 %'],
  ['CW limit ±25 kHz / +50 kHz (B centre)', '+50 / +50 dBc', '+40 / +40 dBc', '+40 / +40 dBc', '+40 / < +30 dBc'],
  ['Reported Δf (mean)', '−1225 Hz (uncal.)', '−79 Hz', '−77 Hz', '+224…295 Hz']],
 cap_dual='Mean over the valid cycles (on-chip 32, AFC off 17, AFC on 15). The single-channel I/Q column is the 23 Nov run (other firmware, 161.985 MHz / 50 ksps).',
 dual_b=[
  '<b>Two channels cost nothing:</b> AFC off, the dual chain is as sensitive as the single-channel one (−106.21 vs −106.19 dBm), and A with B on air at the same time is within the scatter of A alone (8.3 vs 6.6 % at −104 dBm).',
  '<b>AFC trades 0.48 dB for ±4 kHz.</b> With AFC the I/Q path tolerates more offset than the on-chip PHY (whose PER climbs to 40–50 % at ±4 kHz) and is still 0.25 dB more sensitive than on-chip. Live traffic (transmitter offsets of a few hundred Hz to ~1 kHz plus the receiver crystal) is the case the AFC is for.',
  '<b>Selectivity:</b> the B→A alias of the 50 ksps plan is gone (+50 kHz CW now harmless up to +40 dBc, was 100 % PER at +30 dBc). Near the channel the I/Q path still gives up ~10 dB to on-chip (+40 vs +50 dBc at ±25 kHz) — the FG23 I/Q filter and the ESP FIR, not the decoder; −300 kHz is fine on both.',
  '<b>Stable:</b> 50 % points per cycle within ±0.4 dB over 19 h on all paths, no drift.'],
 s_open='7  Open items',
 open=['Live A/B comparison of dual I/Q (AFC on) vs on-chip on ID1 (antenna), like the 23–24 Nov AISBENCH.',
       'I/Q near-channel blocking (+40 dBc at ±25 kHz): FG23 I/Q filter bandwidth / ESP FIR.',
       'On-chip −0.74 dB: LEGACY demod parameters not tuned yet.',
       'On-chip Δf report: scale calibration.',
       'Per-board crystal correction in NVS (ID2 ≈ +13.5 ppm), AY state reset at A1, retune on mode exit.',
       'RF: 162 MHz match / front end (current radio board is matched for 434 MHz).'],
 files='Data and scripts: ionos-sdr-mini-fw/measurements/ionos-mini-2026-11-22-rx and …-11-23-ais-onchip (overnight.csv, overnight.py, analyze_overnight.py); live proxy log ais_bench.json (X99); dual-channel run: …-11-25-ais-dual (overnight3.csv, overnight_dual.py, dual_charts.py).',
)
TX['hu'] = dict(
 title='AIS vétel az ionos-mini-n: I/Q út kontra FG23 on-chip demodulátor',
 sub='Mérési jelentés · műszeres (VSG) és terepi tesztek · 2026. 11. 22–26. · HA7DCD · 2. kiadás: kétcsatornás I/Q (6. fejezet)',
 s_sum='Összefoglaló',
 key=[
  '<b>Tiszta, frekvencián lévő jel:</b> az I/Q út 0,74 dB-lel érzékenyebb. 50 % PER: <b>−106,19 dBm</b> (I/Q, szórás 0,17) vs <b>−105,45 dBm</b> (on-chip, szórás 0,10), 26 ciklus 13 óra alatt, drift nincs.',
  '<b>Frekvenciaeltérés:</b> az on-chip <b>±3 kHz</b>-et tűr (PER ≤ 7,7 % −103 dBm-en), az I/Q demod csak <b>≈ ±1 kHz</b>-et (42 % −1 kHz-en, 52 % +2 kHz-en).',
  '<b>Blokkolás:</b> az on-chip +50 dBc CW-t kibír ±25 és −300 kHz között. Az I/Q +50 dBc-nél elhasal ±25 kHz-en, és a <b>B csatornán lévő vivő bármilyen szinten letakarja az A-t</b> (decimációs alias az 50 ksps-os streamben).',
  '<b>Élő forgalom</b> (ugyanaz az antenna, 5 perc / 5 perc váltás, 14,7 óra számolva): on-chip <b>101 üzenet/h</b>, I/Q <b>81 üzenet/h</b> → <b>1,24×</b>. 74 állomást mindkettő hallott, 20-at csak az I/Q (mind 1 üzenettel, főleg −103…−106 dBm, köztük egy érvénytelen 10 jegyű MMSI), 1-et csak az on-chip.',
  '<b>Táp:</b> hálózatról töltött laptop USB-je + épületföldre fogott antenna → 20 ms-onként 12–17 dB-es erősítésbeesés, a burstök 3 %-a dekódol. Powerbankról: 89 %.',
  '<b>Kétcsatornás I/Q (2. kiadás, 11. 25–26., 34 ciklus / 19 h):</b> A és B <b>egyszerre</b>, egy FG23-ból (162,000 MHz, 100 ksps). Érzékenységben nincs ára: 50 %-os pont <b>−106,21 dBm</b> (AFC ki, szórás 0,17) = az egycsatornás I/Q. A B egyedül és az A+B egyszerre a szóráson belül hozza az A-t. AFC-vel <b>±4 kHz</b> frekvenciatűrés (PER ≤ 15 % −103 dBm-en, jobb az on-chipnél) <b>0,48 dB</b> érzékenységért cserébe (−105,73 dBm). A B→A alias megszűnt: a B-n lévő vivő csak ≥ +50 dBc-től takarja le az A-t.',
  '<b>Ítélet (2. kiadás):</b> papíron most a kétcsatornás, AFC-s I/Q a jobb vevő: on-chip szintű érzékenység (−105,7 vs −105,5 dBm), szélesebb frekvenciatűrés, két csatorna. Az on-chipnek a csatorna közelében ~10 dB-lel több blokkolási tartaléka marad (+50 vs +40 dBc ±25 kHz-en). Következő lépés: élő A/B összevetés ID1-en.'],
 s_setup='1  Mérési elrendezés',
 setup=[
  '<b>Hardver:</b> ionos-mini rev-B3 2L (ESP32-S3 + EFR32FG23, BRD4265B rádiókártya 434 MHz-es illesztéssel — a 162 MHz kívül esik az illesztett sávon, ezért az abszolút szintek relatívak; az eredmény a két út összevetése). ID2 (iroda, kábelen a VSG-n), ID1 (otthon, antennán).',
  '<b>I/Q út:</b> FG23 <font name="DVM">RX_IQDATA_FILTLSB</font>, 50 ksps, 161,985 MHz → SPI → ESP32 <font name="DVM">ais_rx.c</font>: NCO az A csatornára, 6 kHz-es komplex FIR (Q15), FM diszkriminátor, átmintavételezés 48 kHz-re, 5 párhuzamos mintafázis-sáv NRZI/HDLC/CRC-16-tal. Csak A csatorna.',
  '<b>On-chip út:</b> FG23 AIS PHY (2GFSK 9600 Bd, <b>LEGACY</b> demod — a konfigurátor alapértelmezett TRECS_VITERBI-je timing detectet adott, syncet nem), 16 bites sync word 0x80CC/0x7F33 (LSB-first, felvételből mérve), az FG23-on futó <font name="DVM">ais_hw.c</font> csinálja az NRZI/HDLC/CRC-t és a záró flagnél azonnal újraélesít. A keretek AIS1 blokkban mennek az ESP-nek. A vagy B csatorna (egyszerre egy).',
  '<b>Műszer:</b> Signal Hound VSG60A → 40 dB csillapító → kártya; a szintek a kártya bemenetén értendők. Jel: 4 valós 21-es típusú keret, GMSK BT 0,4, 9600 Bd, ITU felfutás + 24 bites training, 10 burst/s, VSG 161 972 850 Hz-en (ID2 kvarcának ≈ +13,5 ppm-es kompenzálása). Pontonként 200 burst, 1,5 s beállás nem számít.'],
 s_hours='2  Mérési kampányok és órák',
 hours=[['Kampány', 'Kártya / hely', 'Időtartam', 'Mennyiség'],
  ['Terepi felvételek (I/Q, SpyServer)', 'ID1, otthon, 2 m-es mágnestalpas radiátoron', '11. 22.: 720 s + 4 × 90 s', '558 burst elemezve (beesések, dekódolás)'],
  ['Terepi élő térkép', 'ID1, otthon (Duna ~1 km)', '11. 22.: 70 perc', '788 NMEA, 82 állomás'],
  ['VSG egyszeri sweepek', 'ID2, iroda, VSG60A', '11. 23., 18:13-ig', 'a teljes mátrix egyszer utanként'],
  ['VSG éjszakai mátrix', 'ID2, iroda, VSG60A', '11. 23. 18:53 → 11. 24. 07:57 (13,1 h)', '26 ciklus, 2118 pont, 479 700 burst'],
  ['Élő AISBENCH (váltakozó)', 'ID1, otthon, antenna', '11. 23. 17:21 → 11. 24. 12:28 (19,1 h)', 'a proxy 14,7 h-t naplózott (utanként 7,36 h): 1339 üzenet, 95 állomás'],
  ['VSG éjszakai mátrix, kétcsatornás I/Q', 'ID2, iroda, VSG60A', '11. 25. 12:57 → 11. 26. 08:07 (19,2 h)', '34 ciklus (2 kizárva), 3196 mérési pont'],
  ['<b>Összesen</b>', '', '<b>32,3 h műszeres (+ nappali sweepek), ≈ 20,5 h terepi</b>', '']],
 cap_tl='A műszeres és a terepi futás átfedett: az ID2 a VSG-n, az ID1 az antennán egyszerre ment.',
 s_inst='3  Műszeres tesztek (VSG60A, ID2)',
 h_sens='3.1  Érzékenység',
 sens='PER a szint függvényében, A csatorna, 26 ciklus átlaga ± szórása. A B csatorna (csak on-chip) a szóráson belül követi az A-t (−104 dBm: 13,4 ± 2,8 %, −106 dBm: 64,6 ± 3,3 %).',
 sens_t=[['dBm', '−100', '−102', '−103', '−104', '−105', '−106', '−107', '−108'],
         ['on-chip', '0', '0,4', '4,2', '14,1', '35,8', '66,8', '91,0', '99,2'],
         ['I/Q', '0', '0,3', '1,5', '6,4', '19,6', '44,5', '72,1', '91,6']],
 cap_sens='PER %, 26 ciklus átlaga. 50 %-os pont: on-chip −105,45 dBm (−105,62…−105,22), I/Q −106,19 dBm (−106,40…−105,75).',
 cap_p50='50 %-os pont ciklusonként, interpolálva. Mindkettő stabil egész éjjel; az I/Q szórása (0,17 dB) kb. kétszerese az on-chipének (0,10 dB).',
 h_foff='3.2  Frekvenciaeltérés',
 foff='−103 dBm-en az on-chip út (PHY AFC, 3,24 kHz tűrés) −3 és +3 kHz között ≤ 7,7 %. Az I/Q demodban nincs frekvenciakövetés: −1 kHz-en 42 %, ±2…3 kHz-en túl ≥ 97 %. A valódi AIS adók néhány száz Hz-től ~1 kHz-ig térnek el, ehhez jön a vevő kvarca — az élő vételt ez dönti el, nem a 0,74 dB.',
 h_cw='3.3  Szelektivitás (CW zavaró)',
 cw='Hasznos jel −100 dBm az A csatornán, CW a jelzett eltérésen és szinten. Az I/Q hibája +50 kHz-en nem szűrőmeredekségi gond: a B csatorna (+40 kHz a 161,985 MHz-es I/Q középtől) az 50 ksps-os streamben az A csatornára tükröződik. Valódi B-forgalom ugyanezt csinálja. 60 dBc-nél a hasznos jel −60 dBFS a VSG-n, a VSG zaja/spurjai is szerepet játszhatnak — a 60 dBc-s oszlop óvatosan kezelendő.',
 h_slot='3.4  Slot-terhelés és B csatorna',
 slot='Burst minden slotban (37,5/s): −96 dBm-en mindkét út 0 % mind a 26 ciklusban; −104 dBm-en on-chip 9,4 ± 1,2 %, I/Q 6,4 ± 1,1 % (ugyanaz a sorrend, mint egyedi burstöknél). Az on-chip újraélesítés a záró flag után elkapja a következő slotot.',
 h_df='3.5  Jelentett frekvenciaeltérés',
 df='Az I/Q Δf éjjel +295 → +224 Hz-re mozdult (ID2 kvarca az iroda hőmérsékletével). Az on-chip Δf (RAIL becslés) még nincs kalibrálva (~255 Hz-es lépcsők, rossz skála) — csak relatív jelzőnek jó.',
 s_field='4  Terepi tesztek (ID1, otthon, Duna ~1 km)',
 h_gl='4.1  Tápoldali földhurok (11. 22.)',
 gl='Hálózati töltőn lévő laptop, az antenna radiátorra fogva, védőföld nélküli házban: a vevő erősítése ~20 ms-onként 2–4 ms-ra 12–17 dB-t esik (a 100 Hz-es vonal +45,6 dB a medián zaj felett; powerbankról +13,3 dB). A vivő fázisa a beesésen át folytonos (mintavesztés nincs); a beesések helye az SPI-blokkhoz képest egyenletes (nem az adatút). Szabály: akkumulátor vagy leválasztott USB, ha az antenna épületföldhöz ér.',
 h_live='4.2  Élő összevetés, AISBENCH (11. 23–24.)',
 live='Öt perc I/Q, öt perc on-chip, ugyanaz az antenna, 19 óra. A proxy 14,7 órát számolt (7,36 h utanként): I/Q 597 üzenet = 81/h, on-chip 742 = 101/h, <b>arány 1,24</b>. A vevő saját számlálója 08:02-ig ugyanezt adja (721 vs 902, 88-88 slot, 1,25). A 13 teljes órából 10-ben az on-chip nyer.',
 cap_st='Állomásonként, élő. Pontozott vonal: egyenlő darabszám. A pontok többsége felette van (on-chip több). A 20 csak-I/Q állomás mindegyike pontosan 1 üzenet −103…−106 dBm jelentett szinten; egy MMSI 10 jegyű (érvénytelen) → ezek egy része véletlenül CRC-helyes zaj, nem gyenge valódi állomás.',
 mix='Üzenettípusok, 11. 22. élő térkép (70 perc, 788 mondat): 21-es AtoN 567 (virtuális folyamkilométer-bóják), 4-es bázisállomás 101, 20/23-as 59, 1–3-as 55, 8-as 4, szemét 2 (40/48-as típus).',
 s_b='5  Menne a B csatorna egyszerre az I/Q úton? (11. 25-i állapot; azóta elkészült, lásd 6. fejezet)',
 b=[
  '<b>On-chip A + I/Q B egyszerre: nem.</b> Az FG23-ban egy vevő van; vagy I/Q-t streamel, vagy az AIS PHY-t futtatja. Natív A+B-hez két rádió kell (vagy ugrálás, ami a tétlen csatornán üzeneteket veszít).',
  '<b>I/Q A + I/Q B: igen, más hangolási tervvel — még nincs megírva és lemérve.</b>',
  'Ma: közép 161,985 MHz, 50 ksps → A −10 kHz-en, B +40 kHz-en, a ±25 kHz-en kívül, −10 kHz-re = az A csatornára tükröződik. Ez a mért „vivő a B-n letakarja az A-t” eredmény.',
  'Terv: közép <b>162,000 MHz, 100 ksps</b> → A −25 kHz, B +25 kHz, mindkettő a ±50 kHz-en belül, ~18 kHz tartalék a sávszélig. Az <font name="DVM">ais_rx.c</font> már most is példányonként egy csatorna saját NCO-val, 25–200 ksps bemenettel → két példány −25 / +25 kHz-en, változatlan kóddal.',
  'Átvitel: az FG23 → ESP 100/200 ksps bizonyított (200 ksps, 9,1 h soak, FG23 LOST 0).',
  'ESP terhelés: a mintánkénti rész (NCO + 6 kHz-es komplex FIR) dupla sebességen, két csatornára ≈ a mai 4×-ese; a 48 kHz-es rész (diszkriminátor, 5 sáv, HDLC) 2×. Még nincs profilozva — TFT waterfall-lal és WiFi-vel együtt kell mérni.',
  'Mellékhatás: a B→A alias megszűnik; a ±25 kHz-es szomszédos eset valódi szomszédcsatorna-eset lesz, amit a 6 kHz-es FIR és az FG23 100 ksps-os decimációja határoz meg — ugyanazzal a CW-mátrixszal újra kell mérni.',
  '<b>Javaslat:</b> (1) kétcsatornás I/Q 162,000 MHz / 100 ksps-on, (2) frekvenciakövetés az <font name="DVM">ais_rx.c</font>-ben (eltérésbecslés a 24 bites trainingből, vagy kártyánkénti kvarckorrekció NVS-ben) — ez hozza vissza az élő 1,24×-es hátrányt, (3) az éjszakai mátrix újrafuttatása A-n és B-n, CW-vel ±25/±50/±100 kHz-en, ESP-profilozással. Ha az I/Q ezután frekvenciatűrésben hozza az on-chipet, ő a jobb vevő: +0,74 dB és két csatorna egy FG23-ból.'],
 s_dual='6  Kétcsatornás I/Q: mérés (2. kiadás, 11. 25–26.)',
 dual=[
  '<b>Megvalósítás</b> (firmware 47d3ff8, ID2): FG23 162,000 MHz-en, 100 ksps (R = 4, 400 kHz-ről). Csatornánként egy DDC (NCO ∓25 kHz + 61 tapes decimáló FIR 25 ksps-ra) táplál egy-egy <font name="DVM">ais_rx</font> példányt; a duplikált kereteket FCS alapján dobja. AFC: csatornánkénti vivőeltérés-követő (AISIQA8 be / AISIQA0 ki). Jel jelenlétében a zajpadló tartva (ez javította az első futás slot-terheléses hibáját: 70 % → 6 % PER). MMSI/típus plauzibilitás-szűrő be. ESP terhelés ≈ egy mag 35 %-a.',
  '<b>Futás:</b> VSG60A → 40 dB → ID2, ugyanazok a hullámformák és szintek, mint a 11. 23-i mátrixban, plusz B csatorna egyedül (E) és A+B egyszerre (F, két burst ugyanabban a slotban, ±25 kHz). Páratlan ciklus AFC be, páros AFC ki; minden ciklusban az on-chip út a referencia. 34 ciklus 19,2 óra alatt. <b>A 11. és 19. ciklus kizárva:</b> pontosan egybeesnek két teljes firmware-fordítással a mérő PC-n (18:37–19:00, 23:13–23:41) — ezekben az ablakokban minden út, az on-chip is −96 dBm-en, elhasalt (a host éhezett, nem a rádió).'],
 dual_t=[['', 'on-chip', 'kétcsat. I/Q, AFC ki', 'kétcsat. I/Q, AFC be', 'egycsat. I/Q (11. 23.)'],
  ['50 %-os pont (dBm)', '−105,48 ± 0,10', '<b>−106,21 ± 0,17</b>', '−105,73 ± 0,21', '−106,19 ± 0,18'],
  ['PER −104 dBm, A', '14,3 %', '6,6 %', '13,5 %', '6,4 %'],
  ['PER −104 dBm, csak B', '14,9 %', '7,1 %', '8,8 %', '—'],
  ['PER −104 dBm, A / B egyszerre', '—', '8,3 / 8,1 %', '14,9 / 9,3 %', '—'],
  ['PER −106 dBm, A / B egyszerre', '—', '46,3 / 50,8 %', '58,8 / 50,7 %', '—'],
  ['Eltérés, PER ≤ 15 % −103 dBm-en', '−3 … +3 kHz', '0 … +1 kHz', '<b>−4 … +4 kHz</b>', '0 … +1 kHz'],
  ['Slot-terhelés −104 dBm', '9,4 %', '6,0 %', '8,0 %', '6,4 %'],
  ['CW határ ±25 kHz / +50 kHz (B közepe)', '+50 / +50 dBc', '+40 / +40 dBc', '+40 / +40 dBc', '+40 / < +30 dBc'],
  ['Jelentett Δf (átlag)', '−1225 Hz (kalibrálatlan)', '−79 Hz', '−77 Hz', '+224…295 Hz']],
 cap_dual='Átlag az érvényes ciklusokra (on-chip 32, AFC ki 17, AFC be 15). Az egycsatornás I/Q oszlop a 11. 23-i futás (másik firmware, 161,985 MHz / 50 ksps).',
 dual_b=[
  '<b>A két csatorna nem kerül semmibe:</b> AFC nélkül a kétcsatornás lánc ugyanolyan érzékeny, mint az egycsatornás (−106,21 vs −106,19 dBm), és az A, miközben a B is adásban van, a szóráson belül hozza a csak-A esetet (8,3 vs 6,6 % −104 dBm-en).',
  '<b>Az AFC 0,48 dB-t ad ±4 kHz-ért.</b> AFC-vel az I/Q út több frekvenciaeltérést tűr, mint az on-chip PHY (annak PER-je ±4 kHz-en 40–50 %-ra ugrik), és még így is 0,25 dB-lel érzékenyebb az on-chipnél. Az élő forgalom (adók néhány száz Hz-től ~1 kHz-ig eltérve, plusz a vevő kvarca) pont az az eset, amire az AFC kell.',
  '<b>Szelektivitás:</b> az 50 ksps-os terv B→A aliasa megszűnt (+50 kHz-es CW most +40 dBc-ig ártalmatlan, korábban +30 dBc-nél 100 % PER). A csatorna közelében az I/Q út még ~10 dB-et ad le az on-chipnek (+40 vs +50 dBc ±25 kHz-en) — ez az FG23 I/Q szűrője és az ESP FIR, nem a dekóder; −300 kHz mindkettőnél rendben.',
  '<b>Stabil:</b> az 50 %-os pontok ciklusonként ±0,4 dB-en belül 19 órán át minden úton, drift nincs.'],
 s_open='7  Nyitott tételek',
 open=['Élő A/B összevetés: kétcsatornás I/Q (AFC be) vs on-chip ID1-en (antenna), mint a 11. 23–24-i AISBENCH.',
       'I/Q csatornaközeli blokkolás (+40 dBc ±25 kHz-en): FG23 I/Q szűrősávszélesség / ESP FIR.',
       'On-chip −0,74 dB: a LEGACY demod paraméterei még nincsenek hangolva.',
       'On-chip Δf jelentés: skálakalibráció.',
       'Kártyánkénti kvarckorrekció NVS-ben (ID2 ≈ +13,5 ppm), AY állapot reset A1-nél, újrahangolás módváltáskor.',
       'RF: 162 MHz-es illesztés / front end (a mostani rádiókártya 434 MHz-re illesztett).'],
 files='Adatok és szkriptek: ionos-sdr-mini-fw/measurements/ionos-mini-2026-11-22-rx és …-11-23-ais-onchip (overnight.csv, overnight.py, analyze_overnight.py); élő proxynapló: ais_bench.json (X99); kétcsatornás futás: …-11-25-ais-dual (overnight3.csv, overnight_dual.py, dual_charts.py).',
)

def build(lang, path):
    t = TX[lang]
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                          title=t['title'], author='HA7DCD')
    doc.addPageTemplates([PageTemplate('p', [Frame(18 * mm, 16 * mm, W, A4[1] - 32 * mm, id='f')], onPage=footer(lang))])
    s = [P(t['title'], 'h0'), P(t['sub'], 'sub'), P(t['s_sum'], 'h1')]
    s += [K(x) for x in t['key']]
    s += [P(t['s_setup'], 'h1')] + [B(x) for x in t['setup']]
    s += [P(t['s_hours'], 'h1'), T(t['hours'], [38 * mm, 40 * mm, 46 * mm, W - 124 * mm]), Spacer(1, 4),
          img(f'timeline_{lang}.png', W, t['cap_tl'])]
    s += [P(t['s_inst'], 'h1'), P(t['h_sens'], 'h2'), P(t['sens']),
          img(f'sens_{lang}.png', W * 0.9),
          T(t['sens_t'], [18 * mm] + [(W - 18 * mm) / 8] * 8), P(t['cap_sens'], 'cap'),
          img(f'p50_{lang}.png', W * 0.9, t['cap_p50'])]
    s += [P(t['h_foff'], 'h2'), P(t['foff']), img(f'foff_{lang}.png', W * 0.9)]
    s += [P(t['h_cw'], 'h2'), P(t['cw']), img(f'cw_{lang}.png', W * 0.95)]
    s += [P(t['h_slot'], 'h2'), P(t['slot']), P(t['h_df'], 'h2'), P(t['df'])]
    s += [P(t['s_field'], 'h1'), P(t['h_gl'], 'h2'), P(t['gl']), img(f'groundloop_{lang}.png', W * 0.85)]
    s += [P(t['h_live'], 'h2'), P(t['live']), img(f'live_{lang}.png', W * 0.9),
          img(f'stations_{lang}.png', W * 0.62, t['cap_st']), P(t['mix'])]
    s += [P(t['s_b'], 'h1')] + [B(x) for x in t['b']]
    s += [P(t['s_dual'], 'h1')] + [B(x) for x in t['dual']]
    s += [T(t['dual_t'], [52 * mm] + [(W - 52 * mm) / 4] * 4), P(t['cap_dual'], 'cap')]
    s += [img(f'dual_sens_{lang}.png', W * 0.9), img(f'dual_p50_{lang}.png', W * 0.9), img(f'dual_foff_{lang}.png', W * 0.9),
          img(f'dual_ab_{lang}.png', W * 0.9), img(f'dual_cw_{lang}.png', W * 0.95)]
    s += [B(x) for x in t['dual_b']]
    s += [P(t['s_open'], 'h1')] + [B(x) for x in t['open']] + [Spacer(1, 6), P(t['files'], 'cap')]
    doc.build(s)

build('en', f'{OUT}/ionos-mini_AIS_report_EN_2026-11-26.pdf')
build('hu', f'{OUT}/ionos-mini_AIS_jelentes_HU_2026-11-26.pdf')
print('ok')

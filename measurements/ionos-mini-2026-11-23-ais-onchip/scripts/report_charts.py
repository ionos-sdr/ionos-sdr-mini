#!/usr/bin/env python3
"""Charts for the AIS report (EN / HU labels).
Run from measurements/ionos-mini-2026-11-23-ais-onchip:  python scripts/report_charts.py <out_dir>
Data: data/overnight.csv (VSG matrix), data/live_bench_2026-11-24.json (live AISBENCH, proxy log)."""
import csv, json, sys, datetime as dt, collections, statistics as S
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

M = 'data/'
OUT = sys.argv[1]
TZ = dt.timezone(dt.timedelta(hours=1))
C_IQ, C_HW, C_3, C_GRID, C_TXT = '#2a78d6', '#eb6834', '#1baf7a', '#e4e3df', '#3d3c37'

L = {
 'en': dict(per='PER (%)', lvl='Level at the board (dBm)', iq='I/Q path (ESP32 demod)', hw='on-chip (FG23 demod)',
            sens='Sensitivity, channel A, 26 cycles (mean ± sd)', p50='50 % point per cycle', p50y='50 % point (dBm)',
            foff='Frequency offset tolerance at −103 dBm (26 cycles)', foffx='Signal offset from channel A (kHz)',
            cw='CW interferer, wanted signal −100 dBm (PER %, mean of 26 cycles)', cwx='CW level above the wanted signal (dBc)',
            cwoff='CW offset', live='Live traffic, ID1 home (Danube), AISBENCH 5 min / 5 min',
            livey='Messages per listening hour', ratio='on-chip / I/Q', hour='Hour (CET)',
            st='Stations: messages per path (live, 14.7 h)', stx='I/Q messages', sty='on-chip messages',
            stc='Mean level (dBm)', tl='Test campaigns, 23–24 Nov 2026', vsgday='ID2 VSG: bring-up, single sweeps',
            vsgn='ID2 VSG: overnight matrix, 26 cycles', live1='ID1 antenna: live AISBENCH', chb='Channel B (on-chip)',
            cyc='cycle time'),
 'hu': dict(per='PER (%)', lvl='Szint a kártya bemenetén (dBm)', iq='I/Q út (ESP32 demod)', hw='on-chip (FG23 demod)',
            sens='Érzékenység, A csatorna, 26 ciklus (átlag ± szórás)', p50='50 %-os pont ciklusonként', p50y='50 %-os pont (dBm)',
            foff='Frekvenciaeltérés-tűrés −103 dBm-en (26 ciklus)', foffx='A jel eltérése az A csatornától (kHz)',
            cw='CW zavaró, hasznos jel −100 dBm (PER %, 26 ciklus átlaga)', cwx='CW szint a hasznos jel felett (dBc)',
            cwoff='CW eltérés', live='Élő forgalom, ID1 otthon (Duna), AISBENCH 5 perc / 5 perc',
            livey='Üzenet / hallgatott óra', ratio='on-chip / I/Q', hour='Óra (CET)',
            st='Állomások: üzenetek utanként (élő, 14,7 h)', stx='I/Q üzenetek', sty='on-chip üzenetek',
            stc='Átlagszint (dBm)', tl='Mérési kampányok, 2026. 11. 23–24.', vsgday='ID2 VSG: élesztés, egyszeri sweepek',
            vsgn='ID2 VSG: éjszakai mátrix, 26 ciklus', live1='ID1 antenna: élő AISBENCH', chb='B csatorna (on-chip)',
            cyc='ciklus ideje'),
}

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#b5b4ad',
                     'axes.labelcolor': C_TXT, 'xtick.color': C_TXT, 'ytick.color': C_TXT,
                     'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.titlecolor': C_TXT,
                     'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False})

rows = list(csv.DictReader(open(M + 'overnight.csv')))
def sel(test, path, **kw):
    return [r for r in rows if r['test'] == test and r['path'] == path and all(r[k] == v for k, v in kw.items())]

def grid(ax):
    ax.grid(True, color=C_GRID, lw=0.6); ax.set_axisbelow(True)

def save(fig, name):
    fig.tight_layout(); fig.savefig(f'{OUT}/{name}', dpi=200); plt.close(fig)

def p50(pts):
    pts = sorted(pts)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if y1 > y2: (x1, y1), (x2, y2) = (x2, y2), (x1, y1)
    for i in range(len(pts) - 1):
        (xa, ya), (xb, yb) = pts[i], pts[i + 1]
        if (ya - 50) * (yb - 50) <= 0 and ya != yb:
            return xa + (50 - ya) * (xb - xa) / (yb - ya)
    return None

def run(lang):
    t = L[lang]
    # 1. sensitivity
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    res = {}
    for path, col, lab, mk in (('iq', C_IQ, t['iq'], 'o'), ('hw', C_HW, t['hw'], 's')):
        by = collections.defaultdict(list)
        for r in sel('A_sens', path): by[float(r['board_dbm'])].append(float(r['per_pct']))
        xs = sorted(by); m = [S.mean(by[x]) for x in xs]; sd = [S.pstdev(by[x]) for x in xs]
        ax.errorbar(xs, m, yerr=sd, color=col, marker=mk, ms=4, lw=2, capsize=3, label=lab)
        res[path] = (xs, m)
    b = collections.defaultdict(list)
    for r in sel('E_chB', 'hw'): b[float(r['board_dbm'])].append(float(r['per_pct']))
    xs = sorted(b); ax.plot(xs, [S.mean(b[x]) for x in xs], color=C_HW, ls='--', marker='^', ms=4, lw=1.2, label=t['chb'])
    ax.axhline(50, color='#8a8980', lw=0.8, ls=':')
    ax.annotate('−105.45', (-105.45, 50), xytext=(-104.2, 58), color=C_HW, fontsize=8, arrowprops=dict(arrowstyle='-', color=C_HW, lw=.6))
    ax.annotate('−106.19', (-106.19, 50), xytext=(-107.9, 30), color=C_IQ, fontsize=8, arrowprops=dict(arrowstyle='-', color=C_IQ, lw=.6))
    ax.set_xlabel(t['lvl']); ax.set_ylabel(t['per']); ax.set_title(t['sens'], loc='left'); ax.set_ylim(-3, 103)
    ax.set_xlim(-108.5, -95.5); grid(ax); ax.legend(loc='upper right', fontsize=8)
    save(fig, f'sens_{lang}.png')

    # 2. 50 % point per cycle over the night
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    for path, col, lab in (('iq', C_IQ, t['iq']), ('hw', C_HW, t['hw'])):
        cyc = collections.defaultdict(list); tm = {}
        for r in sel('A_sens', path):
            cyc[int(r['cycle'])].append((float(r['board_dbm']), float(r['per_pct'])))
            tm.setdefault(int(r['cycle']), dt.datetime.fromisoformat(r['time']))
        xs, ys = [], []
        for c in sorted(cyc):
            v = p50(cyc[c])
            if v is not None: xs.append(tm[c]); ys.append(v)
        ax.plot(xs, ys, color=col, marker='o', ms=3, lw=1.5, label=lab)
    ax.set_ylabel(t['p50y']); ax.set_title(t['p50'], loc='left'); grid(ax); ax.legend(fontsize=8, ncol=2, loc='lower left')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M')); ax.set_ylim(-106.8, -104.8); ax.set_xlabel(t['cyc'])
    save(fig, f'p50_{lang}.png')

    # 3. frequency offset
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for path, col, lab, mk in (('iq', C_IQ, t['iq'], 'o'), ('hw', C_HW, t['hw'], 's')):
        by = collections.defaultdict(list)
        for r in sel('B_foff', path): by[float(r['param']) / 1000].append(float(r['per_pct']))
        xs = sorted(by); m = [S.mean(by[x]) for x in xs]; sd = [S.pstdev(by[x]) for x in xs]
        ax.errorbar(xs, m, yerr=sd, color=col, marker=mk, ms=4, lw=2, capsize=3, label=lab)
    ax.set_xlabel(t['foffx']); ax.set_ylabel(t['per']); ax.set_title(t['foff'], loc='left'); ax.set_ylim(-3, 125)
    grid(ax); ax.legend(fontsize=8, loc='upper center', ncol=2, bbox_to_anchor=(0.5, 1.0))
    save(fig, f'foff_{lang}.png')

    # 4. CW interferer heatmaps
    offs = ['+25', '-25', '+50', '+100', '-300']; dbc = ['30', '40', '50', '60']
    fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.7), sharey=True)
    for ax, path, lab in ((axs[0], 'hw', t['hw']), (axs[1], 'iq', t['iq'])):
        g = np.zeros((len(offs), len(dbc)))
        for i, o in enumerate(offs):
            for j, c in enumerate(dbc):
                v = [float(r['per_pct']) for r in sel('C_cw', path) if cw_match(r['param'], o, c)]
                g[i, j] = S.mean(v) if v else np.nan
        ax.imshow(g, cmap='Blues', vmin=0, vmax=100, aspect='auto')
        for i in range(len(offs)):
            for j in range(len(dbc)):
                ax.text(j, i, f'{g[i,j]:.0f}', ha='center', va='center', fontsize=8, color='white' if g[i, j] > 55 else C_TXT)
        ax.set_xticks(range(len(dbc)), dbc); ax.set_yticks(range(len(offs)), [o + ' kHz' for o in offs])
        ax.set_title(lab, loc='left', fontsize=9); ax.set_xlabel(t['cwx'])
        for s in ax.spines.values(): s.set_visible(False)
        ax.tick_params(length=0)
    axs[0].set_ylabel(t['cwoff'])
    fig.suptitle(t['cw'], x=0.01, ha='left', fontsize=10, fontweight='bold', color=C_TXT)
    save(fig, f'cw_{lang}.png')

    # 5. live hourly
    b = json.load(open(M + 'live_bench_2026-11-24.json'))
    hrs = []
    for k in sorted(b['hours']):
        h = b['hours'][k]
        if h.get('sIQ', 0) > 1200 and h.get('sHW', 0) > 1200:
            hrs.append((k[-2:], h['IQ'] / h['sIQ'] * 3600, h['HW'] / h['sHW'] * 3600))
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    x = np.arange(len(hrs)); w = 0.38
    ax.bar(x - w / 2 - 0.01, [h[1] for h in hrs], w, color=C_IQ, label=t['iq'])
    ax.bar(x + w / 2 + 0.01, [h[2] for h in hrs], w, color=C_HW, label=t['hw'])
    ax.set_xticks(x, [h[0] for h in hrs]); ax.set_xlabel(t['hour']); ax.set_ylabel(t['livey'])
    tot_iq = b['n']['IQ'] / b['sec']['IQ'] * 3600; tot_hw = b['n']['HW'] / b['sec']['HW'] * 3600
    ax.set_title(f"{t['live']}", loc='left'); grid(ax); ax.grid(axis='x', visible=False)
    ax.legend(fontsize=8, ncol=2, loc='upper left', bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, max(h[2] for h in hrs) * 1.3)
    save(fig, f'live_{lang}.png')

    # 6. per-station scatter
    st = b['st']
    px, py, pc = [], [], []
    for k, v in st.items():
        n = v.get('IQ', 0) + v.get('HW', 0)
        if n == 0: continue
        lv = (v.get('dIQ', 0) + v.get('dHW', 0)) / n
        px.append(v.get('IQ', 0) + 0.7); py.append(v.get('HW', 0) + 0.7); pc.append(lv)
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    sc = ax.scatter(px, py, c=pc, cmap='viridis', s=22, edgecolor='white', lw=0.5)
    m = max(max(px), max(py)) * 1.3
    ax.plot([0.7, m], [0.7, m], color='#8a8980', lw=0.8, ls=':')
    ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(0.6, m); ax.set_ylim(0.6, m)
    ax.set_xlabel(t['stx'] + ' (+0.7)'); ax.set_ylabel(t['sty'] + ' (+0.7)'); ax.set_title(t['st'], loc='left', fontsize=9)
    cb = fig.colorbar(sc, ax=ax, shrink=0.85); cb.set_label(t['stc']); grid(ax)
    save(fig, f'stations_{lang}.png')

    # 7. timeline
    fig, ax = plt.subplots(figsize=(6.6, 1.35))
    T = lambda s: dt.datetime.fromisoformat(s)
    bars = [(t['live1'], T('2026-11-23T17:21'), T('2026-11-24T12:28'), C_3),
            (t['vsgn'], T('2026-11-23T18:53'), T('2026-11-24T07:57'), C_HW)]
    for i, (lab, a, z, col) in enumerate(bars):
        ax.barh(i, (z - a).total_seconds() / 86400, left=mdates.date2num(a), color=col, height=0.6)
        ax.text(mdates.date2num(a) + 0.01, i, lab, va='center', fontsize=8, color=C_TXT if col != C_HW else 'white')
    ax.set_yticks([]); ax.xaxis_date(); ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,3,6,9,12,15,18,21])); ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.set_title(t['tl'], loc='left'); grid(ax); ax.grid(axis='y', visible=False)
    ax.spines['left'].set_visible(False)
    save(fig, f'timeline_{lang}.png')
    # 8. ground loop (22 Nov, ID1)
    gl = {'en': (['USB, mains-charged laptop\n(ground loop), 720 s, 398 bursts', 'Powerbank\n90 s, 63 bursts'],
                 'bursts with a ≥1 ms gain dip', 'bursts decoded (CRC-correct)', '% of AIS bursts', 'Field, 22 Nov: supply ground loop'),
          'hu': (['USB, hálózatról töltött laptop\n(földhurok), 720 s, 398 burst', 'Powerbank\n90 s, 63 burst'],
                 'burst ≥1 ms-os erősítésbeeséssel', 'dekódolt burst (CRC-helyes)', 'AIS burstök %-a', 'Terep, 11. 22.: tápoldali földhurok')}[lang]
    fig, ax = plt.subplots(figsize=(6.0, 2.6)); x = np.arange(2); w = 0.36
    d1 = [386 / 398 * 100, 1 / 63 * 100]; d2 = [13 / 398 * 100, 56 / 63 * 100]
    r1 = ax.bar(x - w / 2 - .01, d1, w, color=C_HW, label=gl[1]); r2 = ax.bar(x + w / 2 + .01, d2, w, color=C_IQ, label=gl[2])
    for rr in (r1, r2):
        for r in rr: ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 2, f'{r.get_height():.0f} %', ha='center', fontsize=8, color=C_TXT)
    ax.set_xticks(x, gl[0]); ax.set_ylabel(gl[3]); ax.set_ylim(0, 125); ax.set_title(gl[4], loc='left')
    grid(ax); ax.grid(axis='x', visible=False); ax.legend(fontsize=8, ncol=2, loc='upper left')
    save(fig, f'groundloop_{lang}.png')
    return hrs, tot_iq, tot_hw

def cw_match(p, o, c):
    d, f = p.split('@')
    return d == c and int(f) == int(o) * 1000

if __name__ == '__main__':
    print(sorted(set(r['param'] for r in rows if r['test'] == 'C_cw'))[:12])
    for lg in ('en', 'hu'):
        print(lg, run(lg))

#!/usr/bin/env python3
"""Charts for the dual-channel I/Q section of the AIS report (EN / HU labels).
Run from measurements/ionos-mini-2026-11-25-ais-dual:
    python scripts/dual_charts.py <out_dir> [../ionos-mini-2026-11-23-ais-onchip/data/overnight.csv]
Data: data/overnight3.csv (VSG matrix 25-26 Nov, 34 cycles; odd cycles AFC on = 'iq', even AFC off = 'iq_noafc').
Cycles 11 and 19 are excluded: both coincide with full firmware builds on the measurement PC (18:37-19:00,
23:13-23:41), which starved the VSG/serial host - every path failed at -96 dBm in those windows."""
import sys, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = sys.argv[1]
REF = sys.argv[2] if len(sys.argv) > 2 else '../ionos-mini-2026-11-23-ais-onchip/data/overnight.csv'
EXCL = (11, 19)
d0 = pd.read_csv('data/overnight3.csv')
d = d0[~d0.cycle.isin(EXCL)]
o = pd.read_csv(REF)
C = dict(hw='#eb6834', iq='#1baf7a', iq_noafc='#2a78d6', ref='#8a8984', B='#7a5bd6')
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#b5b4ad',
                     'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False,
                     'axes.titlesize': 10, 'axes.titleweight': 'bold'})
L = {
 'en': dict(per='PER (%)', lvl='Level at the board (dBm)', hw='on-chip (FG23)', iq='dual I/Q, AFC on',
            iq_noafc='dual I/Q, AFC off', ref='single-channel I/Q (23 Nov)', sens='Sensitivity, channel A (32 cycles)',
            foff='Frequency offset tolerance at −103 dBm', foffx='Signal offset from channel A (kHz)',
            ab='Channel A and B, alone and simultaneous (AFC off)', A1='A alone', B1='B alone', A2='A, with B on air',
            B2='B, with A on air', hwA='on-chip A', hwB='on-chip B (A2)',
            p50='50 % point per cycle', p50y='50 % point (dBm)', excl='excluded (PC build)', hour='Time (CET)',
            cw='CW interferer, wanted −100 dBm on A (PER %, mean)', cwx='CW above the wanted signal (dBc)',
            slot='Burst in every slot (37.5/s) at −104 dBm', before='before the floor-hold fix (25 Nov 11:23)', after='after (overnight)'),
 'hu': dict(per='PER (%)', lvl='Szint a kártya bemenetén (dBm)', hw='on-chip (FG23)', iq='kétcsatornás I/Q, AFC be',
            iq_noafc='kétcsatornás I/Q, AFC ki', ref='egycsatornás I/Q (nov. 23.)', sens='Érzékenység, A csatorna (32 ciklus)',
            foff='Frekvenciaeltérés-tűrés −103 dBm-en', foffx='A jel eltérése az A csatornától (kHz)',
            ab='A és B csatorna, külön és egyszerre (AFC ki)', A1='csak A', B1='csak B', A2='A, B is adásban',
            B2='B, A is adásban', hwA='on-chip A', hwB='on-chip B (A2)',
            p50='50 %-os pont ciklusonként', p50y='50 %-os pont (dBm)', excl='kizárva (fordítás a mérő PC-n)', hour='Idő (CET)',
            cw='CW zavaró, hasznos jel −100 dBm az A-n (PER %, átlag)', cwx='CW a hasznos jel felett (dBc)',
            slot='Csomag minden slotban (37,5/s), −104 dBm', before='a zajpadló-tartás javítása előtt (nov. 25. 11:23)', after='utána (éjszaka)'),
}
def grid(ax): ax.grid(True, color='#e4e3df', lw=0.6); ax.set_axisbelow(True)
def save(fig, n): fig.tight_layout(); fig.savefig(f'{OUT}/{n}', dpi=200); plt.close(fig)
def p50(g):
    g = g.sort_values('board_dbm', ascending=False); x, y = g.board_dbm.values, g.per_pct.values
    for i in range(1, len(x)):
        if y[i - 1] < 50 <= y[i]: return x[i - 1] + (50 - y[i - 1]) * (x[i] - x[i - 1]) / (y[i] - y[i - 1])
    return np.nan

for lang, t in L.items():
    # 1 sensitivity
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for p in ('hw', 'iq_noafc', 'iq'):
        s = d[(d.test == 'A_sens') & (d.path == p)].groupby('board_dbm').per_pct.agg(['mean', 'std'])
        ax.errorbar(s.index, s['mean'], yerr=s['std'], color=C[p], marker='o', ms=3.5, lw=1.6, capsize=2, label=t[p])
    s = o[(o.test == 'A_sens') & (o.path == 'iq')].groupby('board_dbm').per_pct.mean()
    ax.plot(s.index, s.values, color=C['ref'], ls='--', lw=1.2, label=t['ref'])
    ax.axhline(50, color='#b5b4ad', lw=0.8, ls=':'); ax.set_xlabel(t['lvl']); ax.set_ylabel(t['per']); ax.set_title(t['sens'])
    ax.invert_xaxis(); grid(ax); ax.legend(fontsize=8); save(fig, f'dual_sens_{lang}.png')
    # 2 p50 per cycle over time
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    for p in ('hw', 'iq_noafc', 'iq'):
        g = d0[(d0.test == 'A_sens') & (d0.path == p)]
        q = g.groupby('cycle').apply(p50); tt = pd.to_datetime(g.groupby('cycle').time.min())
        ok = ~q.index.isin(EXCL)
        ax.plot(tt[ok], q[ok], color=C[p], marker='o', ms=3, lw=1.2, label=t[p])
    for c in EXCL:
        tc = pd.to_datetime(d0[d0.cycle == c].time.min()); ax.axvline(tc, color='#d23c3c', lw=0.8, ls=':')
    ax.plot([], [], color='#d23c3c', ls=':', label=t['excl'])
    ax.set_ylabel(t['p50y']); ax.set_xlabel(t['hour']); ax.set_title(t['p50']); grid(ax); ax.set_ylim(-106.75, -105.15); ax.legend(fontsize=7, ncol=4, loc='lower center')
    import matplotlib.dates as md; ax.xaxis.set_major_formatter(md.DateFormatter('%H:%M'))
    save(fig, f'dual_p50_{lang}.png')
    # 3 frequency offset
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for p in ('hw', 'iq_noafc', 'iq'):
        s = d[(d.test == 'B_foff') & (d.path == p)]; s = s.groupby(s.param.astype(float)).per_pct.mean().sort_index()
        ax.plot(s.index / 1000, s.values, color=C[p], marker='o', ms=3.5, lw=1.6, label=t[p])
    s = o[(o.test == 'B_foff') & (o.path == 'iq')]; s = s.groupby(s.param.astype(float)).per_pct.mean().sort_index()
    ax.plot(s.index / 1000, s.values, color=C['ref'], ls='--', lw=1.2, label=t['ref'])
    ax.set_xlabel(t['foffx']); ax.set_ylabel(t['per']); ax.set_title(t['foff']); grid(ax); ax.legend(fontsize=8)
    save(fig, f'dual_foff_{lang}.png')
    # 4 A / B alone and simultaneous
    lv = [-100, -104, -106]
    def m(test, path, chan):
        s = d[(d.test == test) & (d.path == path) & (d.chan == chan)].groupby('board_dbm').per_pct.mean()
        return [s.get(x, np.nan) for x in lv]
    bars = [(t['A1'], m('A_sens', 'iq_noafc', 'A'), '#2a78d6'), (t['A2'], m('F_AB', 'iq_noafc', 'A'), '#8fb8ea'),
            (t['B1'], m('E_chB', 'iq_noafc', 'B'), C['B']), (t['B2'], m('F_AB', 'iq_noafc', 'B'), '#bba9ea'),
            (t['hwA'], m('A_sens', 'hw', 'A'), C['hw']), (t['hwB'], m('E_chB', 'hw', 'B'), '#f3a986')]
    fig, ax = plt.subplots(figsize=(7.2, 3.0)); w = 0.13
    for k, (lab, v, col) in enumerate(bars):
        x = np.arange(len(lv)) + (k - 2.5) * w
        ax.bar(x, v, w * 0.92, color=col, label=lab)
        for xi, vi in zip(x, v):
            if vi == vi: ax.text(xi, vi + 1, '%.0f' % vi, ha='center', fontsize=6.5)
    ax.set_xticks(range(len(lv))); ax.set_xticklabels(['%d dBm' % x for x in lv]); ax.set_ylabel(t['per'])
    ax.set_title(t['ab']); grid(ax); ax.legend(fontsize=7, ncol=3); save(fig, f'dual_ab_{lang}.png')
    # 5 CW matrix
    offs = [25000, -25000, 50000, 100000, -300000]; dbcs = [30, 40, 50, 60]
    paths = [('hw', d), ('iq_noafc', d), ('iq', d), ('ref', o)]
    fig, axs = plt.subplots(1, 4, figsize=(7.4, 2.5), sharey=True)
    for ax, (p, src) in zip(axs, paths):
        pp = 'iq' if p == 'ref' else p
        s = src[(src.test == 'C_cw') & (src.path == pp)].groupby('param').per_pct.mean()
        M = np.array([[s.get('%d@%d' % (c, f), np.nan) for c in dbcs] for f in offs])
        ax.imshow(M, cmap='RdYlGn_r', vmin=0, vmax=100, aspect='auto')
        for i in range(len(offs)):
            for j in range(len(dbcs)):
                v = M[i, j]
                if v == v: ax.text(j, i, '%.0f' % v, ha='center', va='center', fontsize=7, color='white' if 25 < v < 85 else 'black')
        ax.set_xticks(range(4)); ax.set_xticklabels(dbcs, fontsize=7); ax.set_title(t[p], fontsize=7.5)
        ax.set_yticks(range(len(offs))); ax.set_yticklabels(['%+g kHz' % (f / 1000) for f in offs], fontsize=7)
        ax.set_xlabel('dBc', fontsize=7)
    fig.suptitle(t['cw'], fontsize=9, fontweight='bold'); save(fig, f'dual_cw_{lang}.png')
print('ok')

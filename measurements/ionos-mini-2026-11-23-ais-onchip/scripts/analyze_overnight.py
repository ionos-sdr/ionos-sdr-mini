"""analyze.py — summarise overnight.csv (ID2 + VSG60, 2026-11-23/24) and draw charts"""
import csv, os, sys, statistics as S, datetime as dt, collections as C
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
OUT = sys.argv[1] if len(sys.argv) > 1 else D
rows = list(csv.DictReader(open(os.path.join(D, 'overnight.csv'))))
for r in rows:
    r['t'] = dt.datetime.fromisoformat(r['time']); r['cycle'] = int(r['cycle'])
    r['per'] = float(r['per_pct']); r['lvl'] = float(r['board_dbm'])
    r['df'] = float(r['mean_df']) if r['mean_df'] else None
cycles = sorted({r['cycle'] for r in rows})
full = [c for c in cycles if any(r['cycle'] == c and r['test'] == 'E_chB' for r in rows)]
R = [r for r in rows if r['cycle'] in full]
print('cycles', len(cycles), 'complete', len(full), 'rows', len(rows), 'from', rows[0]['time'], 'to', rows[-1]['time'])
IQC, HWC = '#1f6feb', '#2da44e'
lab = {'iq': 'I/Q', 'hw': 'on-chip'}

def g(test, path, key):
    d = C.defaultdict(list)
    for r in R:
        if r['test'] == test and r['path'] == path: d[r[key]].append(r['per'])
    return d

def p50(levels, pers):
    pts = sorted(zip(levels, pers))
    for (l1, p1), (l0, p0) in zip(pts[::-1], pts[::-1][1:]):   # descending level: l1 > l0
        pass
    pts = sorted(zip(levels, pers), key=lambda x: -x[0])          # strong -> weak
    for (la, pa), (lb, pb) in zip(pts, pts[1:]):
        if pa < 50 <= pb:
            return la + (50 - pa) * (lb - la) / (pb - pa)
    return None

out = []
# ---- A sensitivity
out.append('## A sensitivity (PER %%, mean ± sd over %d cycles)' % len(full))
fig, ax = plt.subplots(figsize=(7, 4.2))
p50s = {}
for path, col in (('iq', IQC), ('hw', HWC)):
    d = g('A_sens', path, 'lvl'); lv = sorted(d, reverse=True)
    m = [S.mean(d[l]) for l in lv]; sd = [S.pstdev(d[l]) for l in lv]
    ax.errorbar(lv, m, yerr=sd, color=col, marker='o', capsize=3, label=lab[path])
    out.append('%s: ' % lab[path] + ', '.join('%g dBm %.1f±%.1f' % (l, a, b) for l, a, b in zip(lv, m, sd)))
    # per-cycle 50 % point
    pc = []
    for c in full:
        rr = [r for r in R if r['test'] == 'A_sens' and r['path'] == path and r['cycle'] == c]
        x = p50([r['lvl'] for r in rr], [r['per'] for r in rr])
        if x is not None: pc.append(x)
    p50s[path] = pc
    out.append('  50%% point %s: mean %.2f dBm, sd %.2f, min %.2f, max %.2f (n=%d)' %
               (lab[path], S.mean(pc), S.pstdev(pc), min(pc), max(pc), len(pc)))
ax.set_xlabel('level at the board (dBm)'); ax.set_ylabel('PER (%)'); ax.set_ylim(-3, 103)
ax.invert_xaxis(); ax.grid(alpha=.3); ax.legend()
ax.set_title('AIS PER vs level, ID2, VSG60, %d cycles overnight' % len(full))
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'overnight_sensitivity.png'), dpi=130); plt.close(fig)

# 50 % point over the night
fig, ax = plt.subplots(figsize=(7, 3.4))
for path, col in (('iq', IQC), ('hw', HWC)):
    ts = []
    for c in full:
        rr = [r for r in R if r['test'] == 'A_sens' and r['path'] == path and r['cycle'] == c]
        x = p50([r['lvl'] for r in rr], [r['per'] for r in rr])
        if x is not None: ts.append((rr[0]['t'], x))
    ax.plot([a for a, _ in ts], [b for _, b in ts], marker='o', color=col, label=lab[path])
ax.set_ylabel('50 % PER level (dBm)'); ax.grid(alpha=.3); ax.legend(); ax.set_title('50 % point through the night')
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'overnight_p50_drift.png'), dpi=130); plt.close(fig)

# frequency drift (native df at strong levels)
fig, ax = plt.subplots(figsize=(7, 3.4))
for path, col in (('iq', IQC), ('hw', HWC)):
    ts = [(r['t'], r['df']) for r in R if r['test'] == 'A_sens' and r['path'] == path and r['lvl'] >= -102 and r['df'] is not None]
    ax.plot([a for a, _ in ts], [b for _, b in ts], '.', color=col, label=lab[path] + ' Δf reported')
    if ts:
        v = [b for _, b in ts]
        out.append('Δf %s (A, ≥ −102 dBm): first-hour mean %.0f Hz, last-hour mean %.0f Hz, range %.0f…%.0f' %
                   (lab[path], S.mean(v[:6]), S.mean(v[-6:]), min(v), max(v)))
ax.set_ylabel('reported Δf (Hz)'); ax.grid(alpha=.3); ax.legend(); ax.set_title('Frequency offset reported per frame, through the night')
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'overnight_df_drift.png'), dpi=130); plt.close(fig)

# ---- B offset
out.append('\n## B frequency offset at −103 dBm (PER %, mean ± sd)')
fig, ax = plt.subplots(figsize=(7, 4))
for path, col in (('iq', IQC), ('hw', HWC)):
    d = g('B_foff', path, 'param'); ks = sorted(d, key=lambda k: int(k))
    m = [S.mean(d[k]) for k in ks]; sd = [S.pstdev(d[k]) for k in ks]
    ax.errorbar([int(k) / 1000 for k in ks], m, yerr=sd, color=col, marker='o', capsize=3, label=lab[path])
    out.append('%s: ' % lab[path] + ', '.join('%+d %.1f±%.1f' % (int(k), a, b) for k, a, b in zip(ks, m, sd)))
ax.set_xlabel('VSG offset (kHz)'); ax.set_ylabel('PER (%)'); ax.set_ylim(-3, 103); ax.grid(alpha=.3); ax.legend()
ax.set_title('Frequency offset tolerance, −103 dBm')
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'overnight_foff.png'), dpi=130); plt.close(fig)

# ---- C CW
out.append('\n## C CW interferer, signal −100 dBm (PER % mean over cycles)')
offs = ['25000', '-25000', '50000', '100000', '-300000']; dbcs = ['30', '40', '50', '60']
for path in ('hw', 'iq'):
    d = g('C_cw', path, 'param')
    for o in offs:
        out.append('%s %+d kHz: ' % (lab[path], int(o) // 1000) + ' / '.join('%.1f' % S.mean(d['%s@%s' % (x, o)]) for x in dbcs) + '  (30/40/50/60 dBc)')

# ---- D slot
out.append('\n## D every slot (37.5/s), PER % mean ± sd')
for path in ('hw', 'iq'):
    d = g('D_slot', path, 'lvl')
    out.append('%s: ' % lab[path] + ', '.join('%g dBm %.2f±%.2f' % (l, S.mean(d[l]), S.pstdev(d[l])) for l in sorted(d, reverse=True)))

# ---- E channel B
out.append('\n## E channel B (on-chip), PER % mean ± sd')
d = g('E_chB', 'hw', 'lvl')
out.append(', '.join('%g dBm %.1f±%.1f' % (l, S.mean(d[l]), S.pstdev(d[l])) for l in sorted(d, reverse=True)))

txt = '\n'.join(out); print(txt)
open(os.path.join(OUT, 'overnight_summary.txt'), 'w', encoding='utf-8').write(txt + '\n')

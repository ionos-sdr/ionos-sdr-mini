"""win_count.py log t0 t1 [pattern] — frames per 5 s bin and total in [t0,t1)"""
import sys
t0, t1 = float(sys.argv[2]), float(sys.argv[3]); pat = sys.argv[4] if len(sys.argv) > 4 else 'AIS RX[HW]'
ts = []
for ln in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = ln.split(' ', 1)
    if len(p) == 2 and pat in p[1] and ('type' in p[1]):
        try: ts.append(float(p[0]))
        except ValueError: pass
w = [t for t in ts if t0 <= t < t1]
print('total %d in %.0f s = %.2f/s (expected 10/s)' % (len(w), t1 - t0, len(w) / (t1 - t0)))
b = {}
for t in w: b[int(t // 5) * 5] = b.get(int(t // 5) * 5, 0) + 1
print(' '.join('%d:%d' % kv for kv in sorted(b.items())))

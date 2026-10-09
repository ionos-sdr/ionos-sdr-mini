"""Schematic style lint - rules L1-L15 of the house schematic style guide (Olimex-level KiCad
schematics), on the .kicad_sch files themselves.  --selftest injects one fault per rule into a
copy of the schematic in memory and demands that every one is caught (a check nobody has seen
fail is not a check).  L15 (ERC) is read from kicad-cli's JSON report.

  L1 grid 1.27      L2 <=3 per node     L3 T without junction   L4 wire through a body
  L5 text overlap   L6 text horizontal  L7 supplies upright     L8 orthogonal wires
  L9 decoupling <=15 mm from a supply pin or rail symbol of its rail
  L10 values/refs   L11 GND wire <=10 mm  L12 A4/A3  L13 title block  L14 global labels
  L15 ERC errors

usage: python lint.py <schematic dir> [--netlist twin/netlist.net] [--erc erc.json] [--selftest]
"""
import sys, os, math, copy, re, json
import sx
from libgeo import LibSym, xform, pin_dir

G = 1.27
CHAR_W = 0.96        # stroke font advance / height, measured on a 250 dpi render
APPROVED_GLOBAL = None   # filled from the original netlist names (see main)
POWER_NETS = {'GND', '3V3', '5V0', '5V_LDO', '3V3_RADIO', '3V3_RADIO_RB', 'VMCU_IN'}

def on_grid(v):
    return abs(v / G - round(v / G)) < 1e-3

def fnum(v):
    return float(v)

class SheetData:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.tree = sx.parse(open(path).read())
        self.load()

    def load(self):
        t = self.tree
        self.libs = {s[1]: LibSym(s) for s in sx.get(t, 'lib_symbols')[1:]}
        self.paper = sx.get(t, 'paper')[1]
        tb = sx.get(t, 'title_block')
        self.title = {e[0]: e[1:] for e in (tb[1:] if tb else [])}
        self.wires = []
        for w in sx.find(t, 'wire'):
            p = sx.get(w, 'pts')
            a = (fnum(p[1][1]), fnum(p[1][2])); b = (fnum(p[2][1]), fnum(p[2][2]))
            self.wires.append((a, b))
        self.juncs = [(fnum(sx.get(j, 'at')[1]), fnum(sx.get(j, 'at')[2])) for j in sx.find(t, 'junction')]
        self.ncs = [(fnum(sx.get(j, 'at')[1]), fnum(sx.get(j, 'at')[2])) for j in sx.find(t, 'no_connect')]
        self.labels = []
        for kind in ('global_label', 'label', 'hierarchical_label'):
            for l in sx.find(t, kind):
                at = sx.get(l, 'at')
                size = fnum(sx.get(sx.get(sx.get(l, 'effects'), 'font'), 'size')[1])
                self.labels.append(dict(kind=kind, name=l[1], at=(fnum(at[1]), fnum(at[2])), ang=fnum(at[3]), size=size))
        self.texts = []
        for x in sx.find(t, 'text'):
            at = sx.get(x, 'at'); eff = sx.get(x, 'effects')
            size = fnum(sx.get(sx.get(eff, 'font'), 'size')[1])
            j = sx.get(eff, 'justify')
            self.texts.append(dict(text=x[1], at=(fnum(at[1]), fnum(at[2])), ang=fnum(at[3]), size=size,
                                   just=[str(v) for v in j[1:]] if j else []))
        self.syms = []
        for s in sx.find(t, 'symbol'):
            lib = self.libs[sx.get(s, 'lib_id')[1]]
            at = sx.get(s, 'at')
            pos = (fnum(at[1]), fnum(at[2])); rot = fnum(at[3]) if len(at) > 3 else 0
            m = sx.get(s, 'mirror'); mirror = str(m[1]) if m else None
            unit = int(sx.get(s, 'unit')[1])
            fields = []
            ref = None
            for p in sx.find(s, 'property'):
                if p[0] == 'property' and p[1] == 'Reference':
                    ref = p[2]
                hidden = any(isinstance(e, list) and e and e[0] == 'hide' and str(e[1]) == 'yes' for e in p)
                pat = sx.get(p, 'at'); eff = sx.get(p, 'effects')
                j = sx.get(eff, 'justify')
                size = fnum(sx.get(sx.get(eff, 'font'), 'size')[1])
                fields.append(dict(name=p[1], value=p[2], at=(fnum(pat[1]), fnum(pat[2])), ang=fnum(pat[3]),
                                   hidden=hidden, size=size, just=[str(v) for v in j[1:]] if j else []))
            pins = []
            for pn in lib.unit_pins(unit):
                pins.append(dict(num=pn['num'], etype=pn['etype'], pos=xform(pn['x'], pn['y'], pos, rot, mirror),
                                 dir=pin_dir(pn['ang'], rot, mirror)))
            b = lib.body(unit)
            bbox = None
            if b:
                c = [xform(b[0], b[1], pos, rot, mirror), xform(b[2], b[3], pos, rot, mirror)]
                bbox = (min(c[0][0], c[1][0]), min(c[0][1], c[1][1]), max(c[0][0], c[1][0]), max(c[0][1], c[1][1]))
            self.syms.append(dict(ref=ref, lib=lib, pos=pos, rot=rot, mirror=mirror, unit=unit, pins=pins,
                                  bbox=bbox, fields=fields, power=lib.power,
                                  dnp=str(sx.get(s, 'dnp')[1]) == 'yes' if sx.get(s, 'dnp') else False))


def tbox(text, at, size, ang, just, center_default=True):
    w = len(text) * CHAR_W * size
    h = size
    hj = 'left' if 'left' in just else 'right' if 'right' in just else 'center'
    vj = 'top' if 'top' in just else 'bottom' if 'bottom' in just else 'center'
    x, y = at
    if ang % 180 == 90:
        w, h = h, w
        x0 = x - w if vj == 'bottom' else x if vj == 'top' else x - w / 2
        y0 = y - h if hj == 'left' else y if hj == 'right' else y - h / 2
    else:
        x0 = x if hj == 'left' else x - w if hj == 'right' else x - w / 2
        y0 = y - h if vj == 'bottom' else y if vj == 'top' else y - h / 2
    return (x0, y0, x0 + w, y0 + h)

def label_box(l):
    w = len(l['name']) * CHAR_W * l['size'] + (l['size'] * 2.0 if l['kind'] == 'global_label' else 0)
    h = l['size'] * (1.9 if l['kind'] == 'global_label' else 1.0)
    x, y = l['at']; a = l['ang'] % 360
    if l['kind'] == 'label':
        if a == 0: return (x, y - h - 0.3, x + w, y - 0.3)
        if a == 180: return (x - w, y - h - 0.3, x, y - 0.3)
        if a == 90: return (x - h - 0.3, y - w, x - 0.3, y)
        return (x - h - 0.3, y, x - 0.3, y + w)
    if a == 0: return (x, y - h / 2, x + w, y + h / 2)
    if a == 180: return (x - w, y - h / 2, x, y + h / 2)
    if a == 90: return (x - h / 2, y - w, x + h / 2, y)
    return (x - h / 2, y, x + h / 2, y + w)

def overlap(a, b, m=0.0):
    return a[0] < b[2] - m and b[0] < a[2] - m and a[1] < b[3] - m and b[1] < a[3] - m

def seg_hits_box(a, b, box, m=0.15):
    x0, y0, x1, y1 = box[0] + m, box[1] + m, box[2] - m, box[3] - m
    if a[0] == b[0]:
        return x0 < a[0] < x1 and max(min(a[1], b[1]), y0) < min(max(a[1], b[1]), y1)
    if a[1] == b[1]:
        return y0 < a[1] < y1 and max(min(a[0], b[0]), x0) < min(max(a[0], b[0]), x1)
    return False

def interior(p, a, b):
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) + 1e-6 < p[1] < max(a[1], b[1]) - 1e-6
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) + 1e-6 < p[0] < max(a[0], b[0]) - 1e-6
    return False

def _k(p):
    return (round(p[0], 3), round(p[1], 3))

def nets(sh):
    """point -> net name (power symbol value or label name) for one sheet."""
    par = {}
    def f(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    def u(a, b):
        par[f(a)] = f(b)
    pts = set()
    for a, b in sh.wires:
        u(_k(a), _k(b)); pts |= {_k(a), _k(b)}
    for s in sh.syms:
        for p in s['pins']:
            f(_k(p['pos'])); pts.add(_k(p['pos']))
    for p in list(pts):
        for a, b in sh.wires:
            if interior(p, a, b):
                u(p, _k(a))
    name = {}
    for s in sh.syms:
        if s['power'] and 'PWR_FLAG' not in s['lib'].name:
            v = [x['value'] for x in s['fields'] if x['name'] == 'Value'][0]
            name[f(_k(s['pins'][0]['pos']))] = v
    for l in sh.labels:
        name[f(_k(l['at']))] = l['name']
    return {p: name.get(f(p)) for p in pts}

def field_visible_angle(f, sym):
    return (f['ang'] + sym['rot']) % 180

def lint(sheets, erc=None):
    E = []
    def err(rule, sh, msg):
        E.append((rule, sh.name, msg))
    refs = {}
    for sh in sheets:
        # L12 / L13
        if sh.paper not in ('A3', 'A4'):
            err('L12', sh, 'paper %s' % sh.paper)
        for k in ('title', 'rev', 'date', 'company'):
            if k not in sh.title or not sh.title[k] or not str(sh.title[k][0]).strip():
                err('L13', sh, 'title block field %s empty' % k)
        pts = []
        for s in sh.syms:
            for p in s['pins']:
                pts.append(('pin %s.%s' % (s['ref'], p['num']), p['pos']))
        for a, b in sh.wires:
            pts += [('wire end', a), ('wire end', b)]
            if a[0] != b[0] and a[1] != b[1]:
                err('L8', sh, 'diagonal wire %s-%s' % (a, b))
        for l in sh.labels:
            pts.append(('label %s' % l['name'], l['at']))
        for j in sh.juncs:
            pts.append(('junction', j))
        for n in sh.ncs:
            pts.append(('no-connect', n))
        # L1
        for what, p in pts:
            if not (on_grid(p[0]) and on_grid(p[1])):
                err('L1', sh, '%s off grid at %s' % (what, p))
        # connectivity nodes
        node = {}
        def add(p, k):
            node.setdefault((round(p[0], 3), round(p[1], 3)), []).append(k)
        for a, b in sh.wires:
            add(a, 'w'); add(b, 'w')
        for s in sh.syms:
            for p in s['pins']:
                add(p['pos'], 'p')
        for l in sh.labels:
            add(l['at'], 'l')
        J = {(round(j[0], 3), round(j[1], 3)) for j in sh.juncs}
        for p, ks in node.items():
            inter = sum(1 for a, b in sh.wires if interior(p, a, b))
            deg = ks.count('w') + ks.count('p') + 2 * inter
            if deg > 3:
                err('L2', sh, '%d-way node at %s' % (deg, p))
            if inter and p not in J and ('w' in ks or 'p' in ks):
                err('L3', sh, 'connection on a wire interior without junction at %s' % (p,))
        # L4 wire through a symbol body
        for s in sh.syms:
            if not s['bbox'] or s['power']:
                continue
            own = {(round(p['pos'][0], 3), round(p['pos'][1], 3)) for p in s['pins']}
            for a, b in sh.wires:
                if (round(a[0], 3), round(a[1], 3)) in own or (round(b[0], 3), round(b[1], 3)) in own:
                    continue
                if seg_hits_box(a, b, s['bbox']):
                    err('L4', sh, 'wire %s-%s runs through %s' % (a, b, s['ref']))
        # L5 text overlaps
        boxes = []
        for s in sh.syms:
            for f in s['fields']:
                if f['hidden']:
                    continue
                ang = (f['ang'] + s['rot']) % 360
                ang = 0 if ang % 180 == 0 else 90
                text = f['value'] + ('A' if f['name'] == 'Reference' and len(s['lib'].units()) > 1 else '')
                boxes.append(('%s.%s' % (s['ref'], f['name']), tbox(text, f['at'], f['size'], ang, f['just'])))
                if field_visible_angle(f, s) == 90:
                    err('L6', sh, '%s %s reads vertically' % (s['ref'], f['name']))
        for l in sh.labels:
            boxes.append(('label %s' % l['name'], label_box(l)))
            if l['ang'] % 180 == 90:
                err('L6', sh, 'label %s is vertical' % l['name'])
        for t in sh.texts:
            boxes.append(('text "%s"' % t['text'][:20], tbox(t['text'], t['at'], t['size'], t['ang'], t['just'])))
            if t['ang'] % 360 != 0:
                err('L6', sh, 'text "%s" not horizontal' % t['text'][:20])
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if overlap(boxes[i][1], boxes[j][1], 0.05):
                    err('L5', sh, '%s overlaps %s' % (boxes[i][0], boxes[j][0]))
        for name, bx in boxes:
            for s in sh.syms:
                if s['bbox'] and not s['power'] and not name.startswith(s['ref'] + '.') and overlap(bx, s['bbox'], 0.1):
                    err('L5', sh, '%s overlaps the body of %s' % (name, s['ref']))
            for a, b in sh.wires:
                if name.startswith('label'):
                    continue
                if seg_hits_box(a, b, bx, 0.05):
                    err('L5', sh, '%s sits on wire %s-%s' % (name, a, b))
        # L7 power symbols upright
        for s in sh.syms:
            if s['power'] and (s['rot'] % 360 != 0 or s['mirror']):
                err('L7', sh, '%s (%s) rotated %g' % (s['ref'], s['lib'].name, s['rot']))
        # L10 values, duplicates
        for s in sh.syms:
            if s['power']:
                continue
            val = [f['value'] for f in s['fields'] if f['name'] == 'Value'][0]
            if not val or val in ('~',) or val.startswith('Conn_'):
                err('L10', sh, '%s value "%s"' % (s['ref'], val))
            refs.setdefault((s['ref'], s['unit']), []).append(sh.name)
        # L11 GND wires
        gnd_pts = set()
        for s in sh.syms:
            if s['power'] and s['lib'].name.endswith(':GND'):
                for p in s['pins']:
                    gnd_pts.add((round(p['pos'][0], 3), round(p['pos'][1], 3)))
        changed = True
        gw = set()
        while changed:
            changed = False
            for k, (a, b) in enumerate(sh.wires):
                ka = (round(a[0], 3), round(a[1], 3)); kb = (round(b[0], 3), round(b[1], 3))
                if k not in gw and (ka in gnd_pts or kb in gnd_pts):
                    gw.add(k); gnd_pts |= {ka, kb}; changed = True
        for k in gw:
            a, b = sh.wires[k]
            if math.hypot(a[0] - b[0], a[1] - b[1]) > 10.0 + 1e-6:
                err('L11', sh, 'GND wire %.1f mm long at %s' % (math.hypot(a[0] - b[0], a[1] - b[1]), a))
        # L14 global labels
        for l in sh.labels:
            if l['kind'] == 'global_label':
                if l['name'] in POWER_NETS:
                    err('L14', sh, 'supply %s drawn as a label' % l['name'])
                elif APPROVED_GLOBAL is not None and l['name'] not in APPROVED_GLOBAL:
                    err('L14', sh, 'global label %s not on the approved list' % l['name'])
        # L9 decoupling caps: a cap between a supply rail and GND must sit within 15 mm of a
        # supply pin of that rail (non-passive pin) or of the rail symbol itself, on this sheet
        net = nets(sh)
        for s_ in sh.syms:
            if not (s_['ref'] or '').startswith('C') or s_['power']:
                continue
            n1 = net.get(_k(s_['pins'][0]['pos'])); n2 = net.get(_k(s_['pins'][1]['pos']))
            if n2 != 'GND' or n1 not in POWER_NETS:
                continue
            cands = []
            for t in sh.syms:
                if t is s_:
                    continue
                for p in t['pins']:
                    if net.get(_k(p['pos'])) == n1 and (t['power'] and 'PWR_FLAG' not in t['lib'].name
                                                        or p.get('etype') in ('power_in', 'power_out')):
                        cands.append(p['pos'])
            p1 = s_['pins'][0]['pos']
            d = min((math.hypot(p1[0] - q[0], p1[1] - q[1]) for q in cands), default=999)
            if d > 15.0 + 1e-6:
                err('L9', sh, '%s on %s is %.1f mm from the nearest %s supply pin / rail symbol' % (s_['ref'], n1, d, n1))
    for (ref, unit), where in refs.items():
        if len(where) > 1:
            E.append(('L10', ','.join(where), 'duplicate %s unit %d' % (ref, unit)))
    if erc is not None:
        d = json.load(open(erc))
        n = sum(1 for s in d['sheets'] for v in s['violations'] if v['severity'] == 'error')
        if n:
            E.append(('L15', 'ERC', '%d ERC errors' % n))
    return E

def selftest(d):
    """One injected fault per rule; every one must be caught."""
    base = load_dir(d)
    clean = lint(base)
    if clean:
        print('selftest needs a clean schematic; it has %d findings' % len(clean)); return 3
    def inj(name, fn):
        sh = copy.deepcopy(base)
        fn(sh)
        got = [e for e in lint(sh) if e[0] == name]
        print('  %-4s %s' % (name, 'CAUGHT' if got else 'MISSED'), (got[0][2][:70] if got else ''))
        return bool(got)
    P = [s for s in base if s.wires and s.syms][0]
    pi = base.index(P)
    def first_wire(sh):
        return sh[pi].wires[0]
    def L1(sh):
        a, b = sh[pi].wires[0]; sh[pi].wires[0] = ((a[0] + 0.5, a[1]), (b[0] + 0.5, b[1]))
    def L2(sh):
        s = [x for x in sh[pi].syms if not x['power'] and x['bbox']][0]; p = s['pins'][0]['pos']
        sh[pi].wires += [(p, (p[0], p[1] - 5.08)), (p, (p[0], p[1] + 5.08)), (p, (p[0] - 5.08, p[1]))]
    def L3(sh):
        a, b = [w for w in sh[pi].wires if w[0][1] == w[1][1] and abs(w[0][0] - w[1][0]) > 5][0]
        m = (round((a[0] + b[0]) / 2 / G) * G, a[1])
        sh[pi].wires.append((m, (m[0], m[1] + 7.62)))
    def L4(sh):
        s = [x for x in sh[pi].syms if not x['power'] and x['bbox']][0]; b = s['bbox']
        cy = round((b[1] + b[3]) / 2 / G) * G
        sh[pi].wires.append(((round((b[0] - 5) / G) * G, cy), (round((b[2] + 5) / G) * G, cy)))
    def L5(sh):
        s = [x for x in sh[pi].syms if not x['power']][0]
        f = [x for x in s['fields'] if x['name'] == 'Reference'][0]
        sh[pi].texts.append(dict(text='OVERLAP', at=f['at'], ang=0, size=1.27, just=[]))
    def L6(sh):
        sh[pi].texts.append(dict(text='VERTICAL', at=(300, 250), ang=90, size=1.27, just=[]))
    def L7(sh):
        s = [x for x in sh[pi].syms if x['power']][0]; s['rot'] = 90
    def L8(sh):
        sh[pi].wires.append(((300.0, 200.0), (302.54, 202.54)))
    def L9(sh):
        for t in sh:
            nt = nets(t)
            for c in t.syms:
                if (c['ref'] or '').startswith('C') and nt.get(_k(c['pins'][1]['pos'])) == 'GND' \
                        and nt.get(_k(c['pins'][0]['pos'])) in POWER_NETS:
                    old = c['pins'][0]['pos']
                    dx = 0.0
                    for p in c['pins']:
                        p['pos'] = (p['pos'][0], p['pos'][1] + 40.64)
                    t.wires.append((old, (old[0], old[1] + 40.64)))
                    # its GND end needs a GND symbol at the new place: reuse the old one by moving it
                    for g in t.syms:
                        if g['power'] and g['lib'].name.endswith(':GND') and \
                                _k(g['pins'][0]['pos']) == _k((c['pins'][1]['pos'][0], c['pins'][1]['pos'][1] - 40.64)):
                            g['pins'][0]['pos'] = c['pins'][1]['pos']
                    return
    def L10(sh):
        s = [x for x in sh[pi].syms if not x['power']][0]
        [f for f in s['fields'] if f['name'] == 'Value'][0]['value'] = '~'
    def L11(sh):
        g = [x for x in sh[pi].syms if x['power'] and x['lib'].name.endswith(':GND')][0]
        p = g['pins'][0]['pos']
        sh[pi].wires.append((p, (p[0] + 20.32, p[1])))
    def L12(sh):
        sh[pi].paper = 'A2'
    def L13(sh):
        sh[pi].title['rev'] = ['']
    def L14(sh):
        sh[pi].labels.append(dict(kind='global_label', name='3V3', at=(300.0, 240.0), ang=0, size=1.27))
    ok = 0
    rules = [L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11, L12, L13, L14]
    for f in rules:
        ok += inj(f.__name__, f)
    print('selftest: caught %d of %d' % (ok, len(rules)))
    return 0 if ok == len(rules) else 3

def load_dir(d):
    return [SheetData(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith('.kicad_sch')]

if __name__ == '__main__':
    d = sys.argv[1]
    if '--approved' in sys.argv:
        APPROVED_GLOBAL = set(open(sys.argv[sys.argv.index('--approved') + 1]).read().split())
    if '--netlist' in sys.argv:
        # approved global names = every deliberately named net of the exported netlist
        nl = sx.parse(open(sys.argv[sys.argv.index('--netlist') + 1], encoding='utf-8').read())
        APPROVED_GLOBAL = {sx.get(n, 'name')[1] for n in sx.find(sx.get(nl, 'nets'), 'net')
                           if not sx.get(n, 'name')[1].startswith(('Net-(', 'unconnected-', '/'))}
    erc = sys.argv[sys.argv.index('--erc') + 1] if '--erc' in sys.argv else None
    if '--selftest' in sys.argv:
        sys.exit(selftest(d))
    E = lint(load_dir(d), erc)
    from collections import Counter
    print(Counter(e[0] for e in E))
    for e in E:
        print('%-4s %-18s %s' % e)
    sys.exit(1 if E else 0)

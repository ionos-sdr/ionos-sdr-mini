"""Library-symbol geometry: pins and body boxes per unit, in lib space (y up)."""
import math, re
import sx

def _num(v):
    return float(v)

class LibSym:
    def __init__(self, node):
        self.node = node
        self.name = node[1]
        self.power = sx.get(node, 'power') is not None
        self.pins = []      # (unit, num, name, x, y, ang, length, etype)
        self.gfx = []       # (unit, xmin, ymin, xmax, ymax)
        base = self.name.split(':')[-1]
        for sub in sx.find(node, 'symbol'):
            m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
            unit = int(m.group(1)) if m else 0
            style = int(m.group(2)) if m else 0
            if style > 1:
                continue
            for e in sub[2:]:
                if not isinstance(e, list):
                    continue
                k = e[0]
                if k == 'pin':
                    at = sx.get(e, 'at')
                    ln = sx.get(e, 'length')
                    nm = sx.get(e, 'name'); nu = sx.get(e, 'number')
                    hidden = any(isinstance(x, list) and x[0] == 'hide' for x in e) or 'hide' in [str(x) for x in e]
                    self.pins.append(dict(unit=unit, num=nu[1], name=nm[1], x=_num(at[1]), y=_num(at[2]),
                                          ang=_num(at[3]) if len(at) > 3 else 0.0,
                                          length=_num(ln[1]) if ln else 0.0, etype=str(e[1]), hidden=hidden))
                elif k == 'rectangle':
                    s = sx.get(e, 'start'); t = sx.get(e, 'end')
                    xs = [_num(s[1]), _num(t[1])]; ys = [_num(s[2]), _num(t[2])]
                    self.gfx.append((unit, min(xs), min(ys), max(xs), max(ys)))
                elif k == 'polyline' or k == 'bezier':
                    pts = sx.get(e, 'pts')
                    xs = [_num(p[1]) for p in pts[1:]]; ys = [_num(p[2]) for p in pts[1:]]
                    self.gfx.append((unit, min(xs), min(ys), max(xs), max(ys)))
                elif k == 'circle':
                    c = sx.get(e, 'center'); r = _num(sx.get(e, 'radius')[1])
                    self.gfx.append((unit, _num(c[1]) - r, _num(c[2]) - r, _num(c[1]) + r, _num(c[2]) + r))
                elif k == 'arc':
                    pts = [sx.get(e, 'start'), sx.get(e, 'mid'), sx.get(e, 'end')]
                    xs = [_num(p[1]) for p in pts]; ys = [_num(p[2]) for p in pts]
                    self.gfx.append((unit, min(xs), min(ys), max(xs), max(ys)))

    def units(self):
        u = sorted({p['unit'] for p in self.pins} | {g[0] for g in self.gfx})
        u = [x for x in u if x > 0]
        return u or [1]

    def unit_pins(self, unit):
        return [p for p in self.pins if p['unit'] in (0, unit)]

    def body(self, unit):
        """Body box (graphics only) in lib space."""
        g = [b for b in self.gfx if b[0] in (0, unit)]
        if not g:
            return None
        return (min(b[1] for b in g), min(b[2] for b in g), max(b[3] for b in g), max(b[4] for b in g))


def xform(px, py, at, rot, mirror):
    """lib point -> schematic point (y down)."""
    x, y = px, py
    if mirror == 'y':
        x = -x
    elif mirror == 'x':
        y = -y
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    xr = x * c - y * s
    yr = x * s + y * c
    return (round(at[0] + xr, 4), round(at[1] - yr, 4))


def pin_dir(ang, rot, mirror):
    """Direction (screen) from the pin's connection point toward the body."""
    a = ang
    dx, dy = round(math.cos(math.radians(a))), round(math.sin(math.radians(a)))
    if mirror == 'y':
        dx = -dx
    elif mirror == 'x':
        dy = -dy
    r = math.radians(rot)
    c, s = round(math.cos(r)), round(math.sin(r))
    xr = dx * c - dy * s
    yr = dx * s + dy * c
    return (xr, -yr)

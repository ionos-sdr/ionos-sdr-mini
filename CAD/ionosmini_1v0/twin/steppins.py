"""Round Z-parallel pins of a STEP file, in the file's root coordinates.

No geometry kernel: walks the assembly graph (REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION
+ ITEM_DEFINED_TRANSFORMATION) and the entity references down to CYLINDRICAL_SURFACE.
"""
import re, sys

NM = r"(?:'[^']*'|\$)"

def _parse(path):
    raw = open(path, "r", errors="ignore").read()
    flat = re.sub(r"\s+", "", raw.split("DATA;", 1)[-1])
    ents = {}
    for m in re.finditer(r"#(\d+)=(.*?);(?=#\d+=|ENDSEC)", flat):
        ents[m.group(1)] = m.group(2)
    return ents

def _vec(s):
    return tuple(float(v) for v in s.split(","))

def step_pins(path, rmin=0.25, rmax=0.8):
    ents = _parse(path)
    pt = lambda i: _vec(re.match(r"CARTESIAN_POINT\(%s,\(([^)]*)\)\)" % NM, ents[i]).group(1))
    dr = lambda i: _vec(re.match(r"DIRECTION\(%s,\(([^)]*)\)\)" % NM, ents[i]).group(1))

    def ax(i):
        m = re.match(r"AXIS2_PLACEMENT_3D\(%s,#(\d+),#(\d+),#(\d+)\)" % NM, ents[i])
        o, z, x = pt(m.group(1)), dr(m.group(2)), dr(m.group(3))
        n = sum(v * v for v in z) ** 0.5; z = tuple(v / n for v in z)
        d = sum(a * b for a, b in zip(x, z)); x = tuple(a - d * b for a, b in zip(x, z))
        n = sum(v * v for v in x) ** 0.5; x = tuple(v / n for v in x)
        y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
        return o, (x, y, z)          # frame: columns x, y, z

    def mat(a):                      # 4x4 from frame (local -> parent)
        o, (x, y, z) = a
        return [[x[0], y[0], z[0], o[0]], [x[1], y[1], z[1], o[1]], [x[2], y[2], z[2], o[2]], [0, 0, 0, 1]]

    def inv(M):
        R = [[M[j][i] for j in range(3)] for i in range(3)]
        t = [-sum(R[i][k] * M[k][3] for k in range(3)) for i in range(3)]
        return [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0, 0, 0, 1]]

    def mul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    I = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    refs = {k: re.findall(r"#(\d+)", v) for k, v in ents.items()}

    # child rep -> (parent rep, transform child->parent)
    up = {}
    for k, v in ents.items():
        if "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION" not in v:
            continue
        m = re.search(r"REPRESENTATION_RELATIONSHIP\(%s,%s,#(\d+),#(\d+)\)" % (NM, NM), v)
        t = re.search(r"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION\(#(\d+)\)", v)
        if not (m and t):
            continue
        idt = re.match(r"ITEM_DEFINED_TRANSFORMATION\(%s,%s,#(\d+),#(\d+)\)" % (NM, NM), ents[t.group(1)])
        T = mul(mat(ax(idt.group(2))), inv(mat(ax(idt.group(1)))))
        up[m.group(1)] = (m.group(2), T)
    # shape rep <-> brep rep links without transform
    same = {}
    for k, v in ents.items():
        if v.startswith("SHAPE_REPRESENTATION_RELATIONSHIP("):
            a, b = re.findall(r"#(\d+)", v)[:2]
            same.setdefault(a, set()).add(b); same.setdefault(b, set()).add(a)

    def to_root(rep, depth=0):
        if depth > 50:
            return I
        if rep in up:
            p, T = up[rep]
            return mul(to_root(p, depth + 1), T)
        for o in same.get(rep, ()):
            if o in up:
                p, T = up[o]
                return mul(to_root(p, depth + 1), T)
        return I

    # which representation owns each cylinder: walk down from every *REPRESENTATION
    owner = {}
    for k, v in ents.items():
        if re.match(r"(ADVANCED_BREP_SHAPE_REPRESENTATION|MANIFOLD_SURFACE_SHAPE_REPRESENTATION|SHAPE_REPRESENTATION)\(", v):
            stack = list(refs[k]); seen = set()
            while stack:
                e = stack.pop()
                if e in seen or e not in ents:
                    continue
                seen.add(e)
                if ents[e].startswith("CYLINDRICAL_SURFACE"):
                    if e not in owner or ents[k].startswith("ADVANCED_BREP"):
                        owner[e] = k
                    continue
                if re.match(r"(GEOMETRIC_REPRESENTATION_CONTEXT|\(GEOMETRIC|REPRESENTATION_CONTEXT)", ents[e]):
                    continue
                stack.extend(refs[e])
    pins = set()
    for e, rep in owner.items():
        m = re.match(r"CYLINDRICAL_SURFACE\(%s,#(\d+),([-0-9.Ee+]+)\)" % NM, ents[e])
        r = float(m.group(2))
        if not (rmin <= r <= rmax):
            continue
        o, (x, y, z) = ax(m.group(1))
        M = to_root(rep)
        zz = [sum(M[i][j] * z[j] for j in range(3)) for i in range(3)]
        if abs(abs(zz[2]) - 1) > 1e-4:
            continue
        p = [sum(M[i][j] * o[j] for j in range(3)) + M[i][3] for i in range(3)]
        pins.add((round(p[0], 3), round(p[1], 3), round(r, 3)))
    return sorted(pins)

if __name__ == "__main__":
    for x in step_pins(sys.argv[1]):
        print(x)

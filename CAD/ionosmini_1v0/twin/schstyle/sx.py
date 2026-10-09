"""Minimal S-expression reader/writer for KiCad files."""
import re
TOK = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')
class Sym(str):
    pass
def parse(text):
    stack = [[]]
    pos = 0; n = len(text)
    while pos < n:
        m = TOK.match(text, pos)
        if not m:
            if text[pos:].strip() == '': break
            raise ValueError('bad at %d: %r' % (pos, text[pos:pos+40]))
        pos = m.end()
        if m.group(1): stack.append([])
        elif m.group(2):
            x = stack.pop(); stack[-1].append(x)
        elif m.group(3) is not None:
            s = m.group(3)[1:-1]
            stack[-1].append(s.replace('\\"', '"').replace('\\\\', '\\'))
        else:
            stack[-1].append(Sym(m.group(4)))
    return stack[0][0]
def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
def dump(x, ind=0):
    if isinstance(x, list):
        if not x: return '()'
        simple = all(not isinstance(e, list) for e in x)
        if simple and len(x) <= 8:
            return '(' + ' '.join(dump(e) for e in x) + ')'
        out = '(' + dump(x[0])
        i = 1
        while i < len(x) and not isinstance(x[i], list):
            out += ' ' + dump(x[i]); i += 1
        for e in x[i:]:
            out += '\n' + '\t' * (ind + 1) + dump(e, ind + 1)
        return out + '\n' + '\t' * ind + ')'
    if isinstance(x, Sym): return str(x)
    if isinstance(x, (int,)): return str(x)
    if isinstance(x, float):
        s = ('%.4f' % x).rstrip('0').rstrip('.')
        return s if s not in ('-0', '') else '0'
    return q(x)
def find(x, key):
    return [e for e in x if isinstance(e, list) and e and e[0] == key]
def get(x, key):
    r = find(x, key); return r[0] if r else None

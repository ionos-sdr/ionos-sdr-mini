# -*- coding: utf-8 -*-
"""ionos-sdr-mini digital twin, layer 1: netlist verification.

Reads the netlist that KiCad exported from the schematic - the same thing
that becomes the board - and checks it against spec_signals.py, which was
written independently from the Silabs schematic and the component
datasheets.  Any disagreement means one of the two is wrong.

Usage:  kicad-python twin_check.py [path\\to\\netlist.net]
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_signals as S

DEFAULT_NET = os.path.join(HERE, "netlist.net")

OK, WARN, FAIL = "PASS", "WARN", "FAIL"
results = []


def check(level, group, msg):
    results.append((level, group, msg))


# --------------------------------------------------------------- netlist
TOK = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+')


def sexp(txt):
    stack, cur = [], []
    for m in TOK.finditer(txt):
        t = m.group(0)
        if t == "(":
            n = []
            cur.append(n)
            stack.append(cur)
            cur = n
        elif t == ")":
            cur = stack.pop()
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur


def kids(n, name):
    return [c for c in n if isinstance(c, list) and c and c[0] == name]


def kid(n, name):
    k = kids(n, name)
    return k[0] if k else None


def load(path):
    root = sexp(io.open(path, encoding="utf-8").read())[0]
    nets, parts = {}, {}
    for c in kids(kid(root, "components") or [], "comp"):
        ref = kid(c, "ref")[1]
        v = kid(c, "value")
        parts[ref] = v[1] if v and len(v) > 1 else ""
    for n in kids(kid(root, "nets") or [], "net"):
        name = kid(n, "name")[1]
        pins = []
        for nd in kids(n, "node"):
            pins.append((kid(nd, "ref")[1], kid(nd, "pin")[1]))
        nets[name] = pins
    return nets, parts


def net_of(nets, ref, pin):
    for name, pins in nets.items():
        if (ref, pin) in pins:
            return name
    return None


# ------------------------------------------------------------- the checks
def build_graph(nets):
    """Pin-to-pin graph; the cut-point parts bridge their own two pins so a
    signal can be traced from the MCU all the way to the socket."""
    adj = {}

    def link(a, b):
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    for name, pins in nets.items():
        if name.startswith("unconnected-"):
            continue
        for i in range(len(pins)):
            for j in range(i + 1, len(pins)):
                link(pins[i], pins[j])
    for part in set(S.CUT_POINTS.values()):
        pins = [p for p in adj if p[0] == part]
        nums = sorted(set(p[1] for p in pins))
        if len(nums) == 2:
            link((part, nums[0]), (part, nums[1]))
    return adj


def path(adj, start, goal):
    """BFS; returns the list of parts the signal passes through."""
    seen, queue = {start: None}, [start]
    while queue:
        cur = queue.pop(0)
        if cur == goal:
            out, n = [], cur
            while n is not None:
                out.append(n)
                n = seen[n]
            return list(reversed(out))
        for nb in adj.get(cur, ()):
            if nb not in seen:
                seen[nb] = cur
                queue.append(nb)
    return None


def check_signals(nets):
    """Trace every specified signal from the MCU pin to the socket pin."""
    adj = build_graph(nets)
    for net, esp, (con, cpin), direction, domain in S.SIGNALS:
        goal = (con, str(cpin))
        if goal not in adj:
            check(FAIL, "signal",
                  "%s: %s pin %d is not connected to anything"
                  % (net, con, cpin))
            continue
        if esp is None:
            check(OK, "signal", "%-11s -> %s pin %-2d" % (net, con, cpin))
            continue
        start = ("IC1", esp)
        p = path(adj, start, goal)
        if p is None:
            # is it on the connector at all, just on the wrong pin?
            other = [q for q in adj if q[0] == con
                     and path(adj, start, q) is not None]
            if other:
                check(FAIL, "signal",
                      "%s: IC1 %s reaches %s pin %s, the Silabs sheet says "
                      "pin %d" % (net, esp, con, other[0][1], cpin))
            else:
                check(FAIL, "signal",
                      "%s: no path from IC1 %s to %s pin %d"
                      % (net, esp, con, cpin))
            continue
        through = [r for r, pin in p if r not in ("IC1", con)]
        uniq = []
        for r in through:
            if r not in uniq:
                uniq.append(r)
        check(OK, "signal", "%-11s IC1 %-5s -> %-4s -> %s pin %-2d"
              % (net, esp, "/".join(uniq) or "direct", con, cpin))


def check_cut_points(nets):
    """One and only one cut point per signal that leaves at the socket."""
    for net, part in S.CUT_POINTS.items():
        rb = net + "_RB"
        pins = nets.get(rb, nets.get(net, []))
        refs = set(r for r, p in pins)
        if part in refs:
            check(OK, "cut", "%-11s cut point %s" % (net, part))
        else:
            check(FAIL, "cut",
                  "%s: expected cut point %s on the socket side, found %s"
                  % (net, part, sorted(refs)))


def check_esp_pins(nets):
    """No forbidden GPIO is used; flag strapping pins; check IO_MUX."""
    used = {}
    for name, pins in nets.items():
        for ref, pin in pins:
            if ref == "IC1":
                used[pin] = name
    for pin, net in sorted(used.items()):
        g = S.ESP_GPIO.get(pin)
        if not isinstance(g, int):
            continue
        open_pin = net.startswith("unconnected-")
        if g in S.FORBIDDEN:
            if open_pin:
                check(OK, "esp32", "GPIO%-2d (%s) correctly left open - %s"
                      % (g, pin, S.FORBIDDEN[g]))
            elif net in ("USB_D+", "USB_D-"):
                check(OK, "esp32", "GPIO%-2d (%s) labelled %s only, no load"
                      % (g, pin, net))
            else:
                check(FAIL, "esp32",
                      "GPIO%-2d (%s) carries %s - reserved for %s"
                      % (g, pin, net, S.FORBIDDEN[g]))
        elif g in S.STRAPPING and not open_pin:
            check(WARN, "esp32",
                  "GPIO%-2d (%s) carries %s - strapping pin: %s"
                  % (g, pin, net, S.STRAPPING[g]))
    # the FG23 slave link wants the IO_MUX pins
    for net in ("FG23_SCLK", "FG23_MOSI", "FG23_CS"):
        pins = [p for r, p in nets.get(net, []) if r == "IC1"]
        if not pins:
            continue
        g = S.ESP_GPIO.get(pins[0])
        if g in S.IOMUX_FSPI:
            check(OK, "esp32", "%-11s on GPIO%-2d = %s (IO_MUX)"
                  % (net, g, S.IOMUX_FSPI[g]))
        else:
            check(WARN, "esp32",
                  "%s on GPIO%s is not an SPI2 IO_MUX pin - it will go "
                  "through the GPIO matrix and lose clock headroom" % (net, g))
    # ADC pins for the ladders
    for node, adcpin, pu, rs, c, sw in S.LADDERS:
        g = S.ESP_GPIO.get(adcpin)
        if g in S.ADC1:
            check(OK, "esp32", "%-11s on GPIO%-2d = %s" % (node, g, S.ADC1[g]))
        else:
            check(FAIL, "esp32", "%s on GPIO%s is not an ADC1 channel"
                  % (node, g))


def check_drivers(nets):
    """More than one driver on a net, or a net with a single pin."""
    OUT = {("U1", "5"): "LDO out"}
    for name, pins in sorted(nets.items()):
        if name.startswith("unconnected-"):
            continue
        if len(pins) < 2:
            check(WARN, "net", "%s has only one pin: %s" % (name, pins))
        drivers = [p for p in pins if p in OUT]
        if len(drivers) > 1:
            check(FAIL, "net", "%s has %d drivers" % (name, len(drivers)))


def check_display(nets):
    """DISP2 against the ER-TFTM024-3 datasheet."""
    for pin, (fn, want) in sorted(S.TFT.items()):
        got = net_of(nets, "DISP2", str(pin))
        if got is None:
            check(FAIL, "tft", "pin %-2d (%s): not connected, expected %s"
                  % (pin, fn, want))
        elif got != want:
            check(FAIL, "tft", "pin %-2d (%s): on %s, expected %s"
                  % (pin, fn, got, want))
        else:
            check(OK, "tft", "pin %-2d %-22s -> %s" % (pin, fn, want))


def check_mezz_power(nets):
    """The fixed supply and ground pins of the mezzanine."""
    want = {("CON1", 2): "GND", ("CON1", 38): "GND",
            ("CON2", 1): "GND", ("CON2", 39): "GND"}
    for (con, pin), net in sorted(want.items()):
        got = net_of(nets, con, str(pin))
        if got == net:
            check(OK, "power", "%s pin %-2d -> %s" % (con, pin, net))
        else:
            check(FAIL, "power", "%s pin %-2d is %s, the Silabs sheet says %s"
                  % (con, pin, got, net))


def check_ladders(nets):
    """Resistor-ladder ADC levels and the RC settling time, analytically."""
    import math
    for node, adcpin, pu, rs, cf, sw in S.LADDERS:
        levels = [("idle", S.VDD_LADDER)]
        for name, r in sw:
            v = S.VDD_LADDER * r / (pu + r)
            levels.append((name, v))
        levels.sort(key=lambda t: t[1])
        worst = min(levels[i + 1][1] - levels[i][1]
                    for i in range(len(levels) - 1))
        # worst-case settling: source impedance seen by C is rs + (pu || r)
        tmax = 0.0
        for name, r in sw:
            rsrc = rs + (pu * r) / (pu + r) if (pu + r) else rs
            tmax = max(tmax, 5.0 * rsrc * cf)
        txt = ", ".join("%s=%.3fV" % (n, v) for n, v in levels)
        check(OK, "ladder", "%s: %s" % (node, txt))
        if worst < 0.25:
            check(FAIL, "ladder",
                  "%s: smallest gap %.3f V is too tight for the ADC" % (node, worst))
        elif worst < 0.4:
            check(WARN, "ladder",
                  "%s: smallest gap only %.3f V" % (node, worst))
        else:
            check(OK, "ladder", "%s: smallest gap %.3f V" % (node, worst))
        check(OK, "ladder", "%s: settles in %.0f us (5 tau)" % (node, tmax * 1e6))
        if any(v > S.ADC_FS for n, v in levels):
            check(WARN, "ladder",
                  "%s: idle level %.2f V is above the %.1f V ADC full scale - "
                  "it will clip, which is fine for 'no key' detection"
                  % (node, S.VDD_LADDER, S.ADC_FS))


def main():
    # options are ignored here, but an unknown flag must not be mistaken for
    # a path - a checker that silently prints nothing is worse than useless
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = args[0] if args else DEFAULT_NET
    if not os.path.exists(path):
        print("netlist not found: %s" % path)
        print("export it first:  kicad-cli sch export netlist --format "
              "kicadsexpr --output twin\\netlist.net ionosSDR_mini.kicad_sch")
        return 2
    nets, parts = load(path)
    print("=" * 74)
    print(" ionos-sdr-mini digital twin - layer 1: netlist vs. source documents")
    print(" netlist: %s" % path)
    print(" %d nets, %d components" % (len(nets), len(parts)))
    print("=" * 74)

    check_signals(nets)
    check_mezz_power(nets)
    check_cut_points(nets)
    check_esp_pins(nets)
    check_display(nets)
    check_drivers(nets)
    check_ladders(nets)

    groups = {}
    for lvl, grp, msg in results:
        groups.setdefault(grp, []).append((lvl, msg))
    for grp in ("signal", "power", "cut", "esp32", "tft", "net", "ladder"):
        if grp not in groups:
            continue
        print("\n--- %s ---" % grp)
        show_all = grp in ("signal", "ladder") or "-v" in sys.argv
        for lvl, msg in groups[grp]:
            if lvl != OK:
                print("  %-4s %s" % (lvl, msg))
            elif show_all:
                print("  ok   %s" % msg)
        npass = sum(1 for l, m in groups[grp] if l == OK)
        print("  %d passed" % npass)

    nf = sum(1 for l, g, m in results if l == FAIL)
    nw = sum(1 for l, g, m in results if l == WARN)
    np_ = sum(1 for l, g, m in results if l == OK)
    print("\n" + "=" * 74)
    print(" RESULT: %d pass, %d warn, %d FAIL" % (np_, nw, nf))
    print("=" * 74)
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

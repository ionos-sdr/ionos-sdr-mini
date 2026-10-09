# -*- coding: utf-8 -*-
"""ionos-sdr-mini digital twin, layer 2: plug the radio board in.

Layer 1 (twin_check.py) asks "does the carrier match its own specification".
This layer asks the question that actually bites on the bench:

    I push the BRD4265B into the two sockets.  Where does each signal
    really end up on the EFR32FG23 - and does anything I wired land
    somewhere underneath that I never meant to touch?

How it works
------------
1.  The carrier netlist (exported from the schematic) gives every copper
    connection on our board.
2.  spec_radioboard.py gives every connection on the Silabs board, read
    off their schematic.
3.  The two are joined at the 80 mezzanine pins into one electrical graph
    of the assembled stack.
4.  An abstract ESP32 model walks a single '1' across the signals it
    drives.  After each step the radio-board model samples its own port
    pins.  The received pattern is compared with the transmitted one.

    A walking one is used on purpose: if two signals are swapped, or one
    is shorted to another under the board, the received matrix is a
    permutation (or has extra ones in a column) and the twin can name
    exactly which signal went where.  No amount of staring at a netlist
    does that as reliably.

The ESP32 model is deliberately crude - a pin that is either driving 0,
driving 1 or high-Z.  Emulating the chip is impossible and pointless
here; mis-wiring is the thing we are hunting.

Usage:  kicad-python twin_plug.py [path\\to\\netlist.net]
"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_signals as S
import spec_radioboard as RB
import twin_check as T            # netlist loader and s-expression reader

DEFAULT_NET = os.path.join(HERE, "netlist.net")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
log = []


def say(level, group, msg):
    log.append((level, group, msg))


# ======================================================================
#  the assembled stack as one electrical graph
# ======================================================================
class Stack(object):
    """Carrier + radio board joined at the sockets.

    Nodes are either a carrier pin ("IC1", "J1_18") or a radio-board node
    name ("PA07", "GND", ...).  Union-find collapses everything that is
    shorted together into one electrical net.
    """

    def __init__(self, nets, parts):
        self.parent = {}
        self.carrier_parent = {}   # the carrier alone, socket not plugged in
        self.nets = nets
        self.parts = parts
        self.bridged = []          # what we treated as a short, for the report
        self._wire_carrier(nets)
        self._wire_series(nets)
        self.carrier_parent = dict(self.parent)   # snapshot before plugging in
        self._plug_in()

    # ---- union-find --------------------------------------------------
    def find(self, a, par=None):
        par = self.parent if par is None else par
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def same(self, a, b):
        return self.find(a) == self.find(b)

    def same_on_carrier(self, a, b):
        """Connected by our own copper only, ignoring the radio board."""
        return (self.find(a, self.carrier_parent)
                == self.find(b, self.carrier_parent))

    # ---- the carrier -------------------------------------------------
    def _wire_carrier(self, nets):
        """Every net on our board is an ideal short between its pins."""
        for name, pins in nets.items():
            if name.startswith("unconnected-"):
                continue
            for i in range(1, len(pins)):
                self.join(pins[0], pins[i])

    def _conducts(self, ref):
        """Does this two-pin part carry the signal through?

        Series zero-ohm links and the bridged solder jumpers do.  Pull-ups,
        ladder resistors and capacitors do not - treating them as shorts
        would hide real mistakes.
        """
        if ref in set(S.CUT_POINTS.values()):
            return True
        v = (self.parts.get(ref) or "").strip().upper()
        return v in ("0R", "0", "0 R", "0OHM", "0 OHM", "R0")

    def _wire_series(self, nets):
        pins_of = {}
        for name, pins in nets.items():
            for ref, pin in pins:
                pins_of.setdefault(ref, set()).add(pin)
        for ref, pins in pins_of.items():
            if len(pins) != 2 or not self._conducts(ref):
                continue
            a, b = sorted(pins)
            self.join((ref, a), (ref, b))
            self.bridged.append(ref)

    # ---- the radio board ---------------------------------------------
    def _plug_in(self):
        """Join each socket pin to whatever the BRD4265B has behind it."""
        self.socket = {}           # (CONx, pin) -> (node, series, note)
        for (sock, pin), _name in RB.MEZZ.items():
            con = RB.CON_OF[sock]
            node, series, note = RB.node_of(sock, pin)
            self.socket[(con, str(pin))] = (node, series, note)
            if node is None:
                continue
            if series is not None and not series[2]:
                continue           # the series part is not mounted
            self.join((con, str(pin)), node)

    # ---- electrical evaluation ---------------------------------------
    def levels(self, drivers):
        """drivers: {node_or_pin: 0/1}.  Returns {net root: level}."""
        out = {}
        for src, lvl in drivers.items():
            r = self.find(src)
            if r in out and out[r] != lvl:
                out[r] = "X"       # two drivers disagree
            elif r not in out:
                out[r] = lvl
        return out

    def read(self, probe, lv):
        return lv.get(self.find(probe), "Z")


# ======================================================================
#  the abstract ESP32
# ======================================================================
class Esp32(object):
    """Just enough ESP32-S3 to toggle a pin and to know what it may not do.

    A pin is 'out0', 'out1' or 'z'.  Nothing else about the chip is
    modelled, and nothing else is needed to catch a wrong connection.
    """

    def __init__(self, ref="IC1"):
        self.ref = ref
        self.state = {}

    def drive(self, header_pin, level):
        self.state[header_pin] = level

    def release_all(self):
        self.state = {}

    def drivers(self):
        return dict(((self.ref, p), v) for p, v in self.state.items())

    def gpio(self, header_pin):
        return S.ESP_GPIO.get(header_pin)


# ======================================================================
#  the checks
# ======================================================================
def esp_pin_of(net):
    for n, esp, cp, d, dom in S.SIGNALS:
        if n == net:
            return esp
    return None


def esp_direction_of(net):
    for n, esp, cp, d, dom in S.SIGNALS:
        if n == net:
            return d
    return None


def check_intent(stack):
    """Static trace: every carrier signal must reach the intended port pin."""
    for net, want in sorted(RB.INTENT.items()):
        pins = stack.nets.get(net) or stack.nets.get(net + "_RB") or []
        if not pins:
            say(FAIL, "intent", "%s: not a net on the carrier" % net)
            continue
        probe = pins[0]
        if not stack.same(probe, want):
            # where did it actually land?
            hits = [n for n in RB.PKG if stack.same(probe, n)]
            hits += [n for n in RB.KIND if n not in ("NC",) and stack.same(probe, n)]
            if hits:
                say(FAIL, "intent", "%-11s should reach %s, it reaches %s"
                    % (net, want, ", ".join(sorted(set(hits)))))
            else:
                say(FAIL, "intent",
                    "%-11s should reach %s, it reaches nothing on the radio "
                    "board" % (net, want))
            continue
        pkg = RB.PKG.get(want)
        say(PASS, "intent", "%-11s -> %-4s %s" % (
            net, want, ("(%s pin %d)" % (RB.MCU_REF, pkg)) if pkg else ""))


def _walk(stack, group, title, sources, sinks, label_src, label_sink):
    """Walk a single 1 across `sources`, watch every node in `sinks`.

    sources : [(net, source_node, expected_sink_node)]
    sinks   : the complete set of nodes that could possibly receive it.

    Driving all the other sources to 0 in the same step is deliberate: a
    short between two of our signals then shows up as a driver collision,
    not merely as a second hot pin.
    """
    for i, (net, src, want) in enumerate(sources):
        drivers = {}
        for j, (n2, s2, w2) in enumerate(sources):
            drivers[s2] = 1 if i == j else 0
        lv = stack.levels(drivers)
        hot = sorted(p for p in sinks if stack.read(p, lv) == 1)
        clash = sorted(p for p in sinks if stack.read(p, lv) == "X")
        if clash:
            say(FAIL, group, "%-11s collides with another driver at %s"
                % (net, ", ".join(label_sink(c) for c in clash)))
            continue
        if hot == [want]:
            say(PASS, group, "%-11s %s -> %s"
                % (net, label_src(src), label_sink(want)))
        elif want in hot:
            say(FAIL, group, "%-11s reaches %s but ALSO %s"
                % (net, label_sink(want),
                   ", ".join(label_sink(p) for p in hot if p != want)))
        elif hot:
            say(FAIL, group, "%-11s never reaches %s - it comes out at %s"
                % (net, label_sink(want),
                   ", ".join(label_sink(p) for p in hot)))
        else:
            say(FAIL, group, "%-11s reaches nothing (expected %s)"
                % (net, label_sink(want)))


def check_walk_down(stack):
    """ESP32 drives, the radio board listens."""
    sources = []
    for net, node in sorted(RB.INTENT.items()):
        d = esp_direction_of(net)
        esp = esp_pin_of(net)
        if esp is None or d not in ("out", "bidir"):
            continue
        sources.append((net, ("IC1", esp), node))
    # every node on the radio board a pulse could possibly land on
    sinks = set(RB.PKG) | set(k for k in RB.KIND if k != "NC")

    def lbl_src(s):
        return "GPIO%-2s" % S.ESP_GPIO.get(s[1], "?")

    def lbl_sink(s):
        p = RB.PKG.get(s)
        return "%s%s" % (s, (" (%s.%d)" % (RB.MCU_REF, p)) if p else "")

    _walk(stack, "down", "ESP32 drives", sources, sinks, lbl_src, lbl_sink)


def check_walk_up(stack):
    """The radio board drives, the ESP32 listens."""
    sources = []
    for net, node in sorted(RB.INTENT.items()):
        if RB.RB_DIRECTION.get(node) not in ("out", "bidir"):
            continue
        esp = esp_pin_of(net)
        if esp is None:
            say(WARN, "up", "%-11s (%s) is an FG23 output but goes to no "
                "ESP32 pin - test point only" % (net, node))
            continue
        sources.append((net, node, ("IC1", esp)))
    # every ESP32 pin on the board, so a pulse landing on the wrong GPIO shows
    sinks = set()
    for name, pins in stack.nets.items():
        for ref, pin in pins:
            if ref == "IC1":
                sinks.add((ref, pin))

    def lbl_src(s):
        return "%-4s" % s

    def lbl_sink(s):
        return "GPIO%s" % S.ESP_GPIO.get(s[1], s[1])

    _walk(stack, "up", "FG23 drives", sources, sinks, lbl_src, lbl_sink)


def check_under_the_board(stack):
    """Every socket pin our carrier touches, judged from the radio side."""
    for (con, pin), (node, series, note) in sorted(
            stack.socket.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        net = None
        for name, pins in stack.nets.items():
            if (con, pin) in pins:
                net = name
                break
        used = net is not None and not net.startswith("unconnected-")
        if not used:
            continue
        if node is None:
            others = [q for q in stack.nets[net] if tuple(q) != (con, pin)]
            if others and all(str(q[0]).startswith("TP") for q in others):
                # pin map v2: VRF_IN (P201-40) runs to a test point only - harmless on an open pin
                say(WARN, "socket", "%s pin %-2s carries %s to test point %s only; the radio "
                    "board leaves that pin open (%s)" % (con, pin, net,
                    ", ".join(str(q[0]) for q in others), note))
                continue
            say(FAIL, "socket", "%s pin %-2s carries %s, but the radio board "
                "leaves that pin open (%s)" % (con, pin, net, note))
            continue
        kind = RB.KIND.get(node, "mcu")
        if kind == "radio_out":
            say(FAIL, "socket", "%s pin %-2s carries %s into %s, which the "
                "radio board drives" % (con, pin, net, node))
        elif series is not None and not series[2]:
            say(FAIL, "socket", "%s pin %-2s carries %s, but %s is not "
                "mounted on the radio board" % (con, pin, net, series[0]))
        else:
            say(PASS, "socket", "%s pin %-2s %-16s -> %-12s %s"
                % (con, pin, net, node, note))


def check_aliases(stack):
    """A radio-board node sits on more than one socket pin.  Those other
    pins must stay open on the carrier, or the signal is shorted under the
    board where nobody can see it."""
    for net, node in sorted(RB.INTENT.items()):
        here = RB.pins_of_node(node)
        if len(here) < 2:
            continue
        # a pin that is definitely on our own signal's copper
        probe = (stack.nets.get(net) or stack.nets.get(net + "_RB") or [None])[0]
        others, bad = [], []
        for sock, pin, series, note in here:
            con = RB.CON_OF[sock]
            tag = "%s.%d" % (con, pin)
            cur = None
            for name, pins in stack.nets.items():
                if (con, str(pin)) in pins:
                    cur = name
                    break
            if cur is None or cur.startswith("unconnected-"):
                others.append(tag)
                continue
            # Named or auto-named, what matters is whether this pin is on
            # OUR signal's copper.  Series parts rename the net, so compare
            # electrically, on the carrier alone.
            if probe is not None and stack.same_on_carrier((con, str(pin)), probe):
                continue
            bad.append("%s carries %s" % (tag, cur))
        if bad:
            say(FAIL, "alias", "%s is also on %s - SHORT under the board"
                % (net, "; ".join(bad)))
        elif others:
            say(PASS, "alias", "%-11s (%s) is also on %s - correctly left open"
                % (net, node, ", ".join(others)))


def check_direction(stack):
    """Our idea of who drives a signal against the radio board's."""
    ours = dict((net, d) for net, esp, cp, d, dom in S.SIGNALS)
    for net, node in sorted(RB.INTENT.items()):
        theirs = RB.RB_DIRECTION.get(node)
        mine = ours.get(net)
        if theirs is None or mine is None or mine == "power":
            continue
        ok = ((mine == "in" and theirs in ("out", "bidir"))
              or (mine == "out" and theirs in ("in", "bidir"))
              or "bidir" in (mine, theirs))
        if ok:
            say(PASS, "dir", "%-11s ESP32 %-5s / FG23 %-5s" % (net, mine, theirs))
        else:
            say(FAIL, "dir", "%-11s both sides are %s - nobody drives it"
                % (net, mine))


def check_supplies(stack):
    """The power pins of the mezzanine, from the radio board's side."""
    for node, what in (("3V3", "the radio board's 3.3 V rail"),
                       ("VMCU_IN", "the EFR32 supply, via R201 0R"),
                       ("GND", "ground")):
        pins = RB.pins_of_node(node)
        fed = []
        for sock, pin, series, note in pins:
            con = RB.CON_OF[sock]
            for name, nps in stack.nets.items():
                if (con, str(pin)) in nps and not name.startswith("unconnected-"):
                    fed.append("%s.%d=%s" % (con, pin, name))
        if fed:
            say(PASS, "power", "%-8s %-32s fed by %s"
                % (node, what, ", ".join(fed)))
        else:
            say(WARN, "power", "%-8s %-32s is not fed by the carrier"
                % (node, what))
    # 5 V and USB are optional - say so rather than staying silent
    for node, why in (("5V", "the radio board does not need it for RX/TX"),
                      ("USB_VBUS", "no USB on the radio board in this build"),
                      ("USB_VREG", "radio-board output, must stay open")):
        pins = RB.pins_of_node(node)
        used = []
        for sock, pin, series, note in pins:
            con = RB.CON_OF[sock]
            for name, nps in stack.nets.items():
                if (con, str(pin)) in nps and not name.startswith("unconnected-"):
                    used.append("%s.%d=%s" % (con, pin, name))
        if used:
            say(WARN, "power", "%-8s is driven by the carrier (%s)"
                % (node, ", ".join(used)))
        else:
            say(PASS, "power", "%-8s left open - %s" % (node, why))


# ======================================================================
#  self-test: break the board on purpose and prove the twin notices
# ======================================================================
FAULTS = [
    ("two signals swapped at the socket",
     lambda nets: _swap_pins(nets, ("CON2", "13"), ("CON2", "11"))),
    ("one signal moved one pin over",
     lambda nets: _move_pin(nets, ("CON2", "15"), ("CON2", "17"))),
    ("a spare socket pin tied to a live signal",
     lambda nets: _add_pin(nets, "FG23_CMD", ("CON1", "9"))),
    ("a signal landing on a pin the radio board leaves open",
     lambda nets: _move_pin(nets, ("CON2", "9"), ("CON2", "25"))),
]


def _copy(nets):
    return dict((k, list(v)) for k, v in nets.items())


def _net_of(nets, pin):
    for name, pins in nets.items():
        if pin in pins:
            return name
    return None


def _swap_pins(nets, a, b):
    na, nb = _net_of(nets, a), _net_of(nets, b)
    if na is None or nb is None:
        return nets
    nets[na] = [b if p == a else p for p in nets[na]]
    nets[nb] = [a if p == b else p for p in nets[nb]]
    return nets


def _move_pin(nets, frm, to):
    n = _net_of(nets, frm)
    if n is None:
        return nets
    nets[n] = [to if p == frm else p for p in nets[n]]
    return nets


def _add_pin(nets, net, pin):
    if net in nets:
        nets[net] = nets[net] + [pin]
    return nets


def selftest(nets, parts):
    """Does the twin actually catch a wrong connection?

    A verification tool nobody has ever seen fail is a tool nobody should
    trust.  Each fault below is injected into a copy of the netlist; the
    twin must report at least one FAIL for it.
    """
    global log
    print("\n" + "=" * 76)
    print(" SELF-TEST - four deliberate faults, the twin must catch all four")
    print("=" * 76)
    ok = True
    for title, mutate in FAULTS:
        saved = log
        log = []
        broken = mutate(_copy(nets))
        st = Stack(broken, parts)
        check_intent(st)
        check_walk_down(st)
        check_walk_up(st)
        check_under_the_board(st)
        check_aliases(st)
        fails = [m for l, g, m in log if l == FAIL]
        log = saved
        if fails:
            print("  caught   %-46s %d finding(s)" % (title, len(fails)))
            print("           -> %s" % fails[0])
        else:
            print("  MISSED   %-46s" % title)
            ok = False
    print("=" * 76)
    print(" self-test: %s" % ("all four faults caught" if ok
                              else "THE TWIN MISSED A FAULT"))
    print("=" * 76)
    return ok


# ======================================================================
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = args[0] if args else DEFAULT_NET
    if not os.path.exists(path):
        print("netlist not found: %s" % path)
        print('export it first:  kicad-cli sch export netlist --format '
              'kicadsexpr --output twin\\netlist.net ionosSDR_mini.kicad_sch')
        return 2
    nets, parts = T.load(path)
    stack = Stack(nets, parts)
    esp = Esp32()

    print("=" * 76)
    print(" ionos-sdr-mini digital twin - layer 2: the radio board is plugged in")
    print(" carrier : %s   (%d nets, %d parts)" % (path, len(nets), len(parts)))
    print(" radio   : %s   %s" % (RB.BOARD, RB.MCU))
    print(" bridged : %s" % ", ".join(sorted(set(stack.bridged))))
    print("=" * 76)

    check_intent(stack)
    check_walk_down(stack)
    check_walk_up(stack)
    check_under_the_board(stack)
    check_aliases(stack)
    check_direction(stack)
    check_supplies(stack)

    groups = {}
    for lvl, grp, msg in log:
        groups.setdefault(grp, []).append((lvl, msg))
    titles = [
        ("intent", "static trace: carrier net -> EFR32 port pin"),
        ("down", "walking-one, ESP32 -> FG23: where does the pulse come out"),
        ("up", "walking-one, FG23 -> ESP32: who hears the radio board"),
        ("socket", "every socket pin we touch, seen from the radio board"),
        ("alias", "the same FG23 node on a second socket pin"),
        ("dir", "who drives what"),
        ("power", "supply and ground pins"),
    ]
    verbose = "-q" not in sys.argv
    for grp, title in titles:
        if grp not in groups:
            continue
        print("\n--- %s : %s" % (grp, title))
        for lvl, msg in groups[grp]:
            if lvl != PASS:
                print("  %-4s %s" % (lvl, msg))
            elif verbose:
                print("  ok   %s" % msg)

    nf = sum(1 for l, g, m in log if l == FAIL)
    nw = sum(1 for l, g, m in log if l == WARN)
    np_ = sum(1 for l, g, m in log if l == PASS)
    print("\n" + "=" * 76)
    print(" RESULT: %d pass, %d warn, %d FAIL" % (np_, nw, nf))
    print("=" * 76)

    if "--selftest" in sys.argv:
        if not selftest(nets, parts):
            return 3
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

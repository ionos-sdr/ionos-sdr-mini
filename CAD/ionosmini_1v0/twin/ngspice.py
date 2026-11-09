# -*- coding: utf-8 -*-
"""Minimal ngspice driver.

KiCad ships ngspice as a shared library, so layer 3 needs NOTHING installed:
we drive C:\\Program Files\\KiCad\\10.0\\bin\\ngspice.dll through its own
shared-library API.  The same decks are written out as plain .cir files, so
they can also be opened in QucsStudio or KiCad's simulator by hand.
"""
import ctypes, os, sys

CANDIDATES = [
    r"C:\Program Files\KiCad\10.0\bin\ngspice.dll",
    r"C:\Program Files\KiCad\9.0\bin\ngspice.dll",
    "libngspice.so.0", "libngspice.so",
]


class Spice(object):
    def __init__(self):
        self.lib = None
        self.out = []
        for p in CANDIDATES:
            try:
                d = os.path.dirname(p)
                if d and os.path.isdir(d) and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(d)
                self.lib = ctypes.CDLL(p)
                self.path = p
                break
            except Exception:
                continue
        if self.lib is None:
            raise RuntimeError("ngspice shared library not found")
        self._bind()

    def _bind(self):
        L = self.lib
        SC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                              ctypes.c_void_p)
        CE = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool,
                              ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        SD = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.c_void_p)
        SI = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_void_p)
        BG = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int,
                              ctypes.c_void_p)

        @SC
        def _char(msg, _i, _u):
            self.out.append(msg.decode("latin1", "replace"))
            return 0

        @SC
        def _stat(msg, _i, _u):
            return 0

        @CE
        def _exit(status, imm, quit_, _i, _u):
            self.out.append("[ngspice exit %d]" % status)
            return 0

        @SD
        def _data(p, n, _i, _u):
            return 0

        @SI
        def _init(p, _i, _u):
            return 0

        @BG
        def _bg(run, _i, _u):
            return 0

        self._cb = (_char, _stat, _exit, _data, _init, _bg)
        L.ngSpice_Init.restype = ctypes.c_int
        if L.ngSpice_Init(_char, _stat, _exit, _data, _init, _bg, None) != 0:
            raise RuntimeError("ngSpice_Init failed")
        L.ngSpice_CurPlot.restype = ctypes.c_char_p

        class VI(ctypes.Structure):
            _fields_ = [("v_name", ctypes.c_char_p), ("v_type", ctypes.c_int),
                        ("v_flags", ctypes.c_short),
                        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
                        ("v_compdata", ctypes.c_void_p),
                        ("v_length", ctypes.c_int)]
        self.VI = VI
        L.ngGet_Vec_Info.restype = ctypes.POINTER(VI)

    def run(self, deck):
        """deck: list of SPICE lines (no trailing newline). Returns {name: [values]}."""
        self.out = []
        self.lib.ngSpice_Command(b"destroy all")
        lines = [l.encode("latin1") for l in deck]
        arr = (ctypes.c_char_p * (len(lines) + 1))()
        for i, l in enumerate(lines):
            arr[i] = l
        arr[len(lines)] = None
        if self.lib.ngSpice_Circ(arr) != 0:
            raise RuntimeError("ngSpice_Circ failed:\n" + "\n".join(self.out[-8:]))
        self.lib.ngSpice_Command(b"run")
        plot = self.lib.ngSpice_CurPlot()
        self.lib.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)
        v = self.lib.ngSpice_AllVecs(plot)
        res = {}
        i = 0
        while v[i]:
            name = v[i].decode()
            vi = self.lib.ngGet_Vec_Info(name.encode())
            if vi:
                n = vi.contents.v_length
                res[name] = [vi.contents.v_realdata[k] for k in range(n)]
            i += 1
        return res


def write_deck(path, deck):
    import io
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        "\n".join(deck) + "\n")

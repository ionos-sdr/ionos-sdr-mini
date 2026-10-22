"""jlc_pack - JLCPCB fabrication + assembly pack from the KiCad project, in one run.

Writes fab/jlc_<variant>_<date>/:
  gerber/                      Gerbers (Protel names, no X2) + Excellon drill (PTH/NPTH apart, mm)
  <name>_gerber.zip            upload this as the PCB
  <name>_BOM_JLC.csv           Comment, Designator, Footprint, LCSC Part #   (JLC column names)
  <name>_CPL_JLC.csv           Designator, Mid X, Mid Y, Layer, Rotation     (JLC column names)
  pack_report.txt              what went in, what was left out and why
The JLC-assembled parts are the SMD passives, the LDO and the keys. Left out on purpose
(hand-fitted or not parts at all): displays, the DevKit, the Samtec sockets, the debug header,
solder jumpers, test points, mounting holes, and every DNP part.
Gate: KiCad DRC (errors only, with schematic parity) must be clean, or nothing is written.
LCSC numbers: fab/jlc_lcsc.csv, keyed by Value + Footprint, checked against the BOM: a fitted
part without an LCSC number stops the run.

usage: "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" fab/jlc_pack.py [variant-name]
"""
import os, sys, csv, json, zipfile, datetime, subprocess, collections, re

CLI = os.environ.get('KICAD_CLI', r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PRJ = os.path.join(REPO, 'CAD', 'ionosmini_1v0')
PCB = os.path.join(PRJ, 'ionosSDR_mini.kicad_pcb')
SCH = os.path.join(PRJ, 'ionosSDR_mini.kicad_sch')
EXCLUDE = re.compile(r'^(DISP\d+|IC\d+|JP\d+|TP\d+|H\d+)$')     # CON1/CON2 (Samtec) are JLC-assembled
# BOM Comment override per LCSC part, when the part ordered differs from the schematic Value
COMMENT = {'C17227108': 'TFM-120-02-L-D-K-TR'}      # TFC-120-02 out of stock -> Samtec TFM (male, unshrouded)
# CPL rotation offset per LCSC part, measured in the JLC placement preview (magenta pin 1 vs KiCad pin 1).
# Per JLC library model, not per package: AP2112K (SOT-23-5) needed +270 on the CW trainer.
ROT = {'C80670': 180}                                # LP5907MFX-3.3, 2026-10-22 preview
WHY = {'DISP': 'display module, fitted by hand', 'IC': 'ESP32-S3 DevKit on headers, fitted by hand',
       'JP': 'solder jumper, copper only',
       'TP': 'test pad, copper only', 'H': 'mounting hole'}


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode not in (0, 5):     # kicad-cli drc returns 5 when violations exist
        sys.exit('failed: %s\n%s%s' % (' '.join(args), r.stdout, r.stderr))
    return r


def copper_layers():
    txt = open(PCB, encoding='utf-8').read()
    # any layer type: rev-B3's In2.Cu is a 'power' layer (GND_PWR) - matching only 'signal'
    # silently dropped it from the Gerbers (caught on the first 4L run, 2026-10-22)
    head = txt[:txt.find('(setup')]
    inner = sorted(set(re.findall(r'\(\d+ "(In\d+\.Cu)" (?:signal|power|mixed|jumper)', head)),
                   key=lambda s: int(s[2:-3]))
    return ['F.Cu'] + inner + ['B.Cu']


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else ('4L' if len(copper_layers()) > 2 else '2L')
    date = datetime.date.today().strftime('%Y%m%d')
    name = 'ionos-sdr-mini_revB3_%s_%s' % (variant, date)
    out = os.path.join(HERE, 'jlc_%s_%s' % (variant, date))
    gdir = os.path.join(out, 'gerber')
    os.makedirs(gdir, exist_ok=True)
    rep = ['%s  %s' % (name, datetime.datetime.now().isoformat(timespec='seconds'))]

    # ---- gate: DRC errors + schematic parity
    js = os.path.join(out, 'drc.json')
    run([CLI, 'pcb', 'drc', '--refill-zones', '--schematic-parity', '--severity-error',
         '--format', 'json', '-o', js, PCB])
    d = json.load(open(js, encoding='utf-8'))
    nerr = len(d['violations']) + len(d['unconnected_items']) + len(d.get('schematic_parity', []))
    rep.append('DRC: %d errors, %d unconnected, %d parity' % (len(d['violations']), len(d['unconnected_items']),
                                                             len(d.get('schematic_parity', []))))
    if nerr:
        open(os.path.join(out, 'pack_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
        sys.exit('DRC not clean - no pack written (see drc.json)')

    # ---- Gerbers + drill
    cu = copper_layers()
    layers = cu + ['F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask', 'Edge.Cuts']
    run([CLI, 'pcb', 'export', 'gerbers', '-o', gdir + os.sep, '--layers', ','.join(layers),
         '--no-x2', '--subtract-soldermask', '--check-zones', PCB])
    run([CLI, 'pcb', 'export', 'drill', '-o', gdir + os.sep, '--format', 'excellon', '--excellon-units', 'mm',
         '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate', '--excellon-separate-th',
         '--drill-origin', 'absolute', '--generate-map', '--map-format', 'gerberx2', PCB])
    files = sorted(os.listdir(gdir))
    ncu = len([f for f in files if re.search(r'\.(gtl|gbl|g\d+)$', f)])
    if ncu != len(cu):
        sys.exit('copper Gerbers: %d files for %d copper layers %s' % (ncu, len(cu), cu))
    zp = os.path.join(out, name + '_gerber.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(gdir, f), f)
    rep.append('Gerber zip: %d files, copper %s' % (len(files), ', '.join(cu)))

    # ---- BOM (fitted parts) + LCSC map
    bom_raw = os.path.join(out, 'bom_raw.csv')
    run([CLI, 'sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,${DNP}',
         '--group-by', '', '--ref-range-delimiter', '', '--exclude-dnp', '-o', bom_raw, SCH])
    lcsc = {(r['Value'], r['Footprint']): r for r in csv.DictReader(open(os.path.join(HERE, 'jlc_lcsc.csv'), encoding='utf-8'))}
    groups = collections.OrderedDict(); left = collections.defaultdict(list); missing = []
    for r in csv.DictReader(open(bom_raw, encoding='utf-8')):
        refs = [x.strip() for x in r['Reference'].split(',') if x.strip()]
        for ref in refs:
            if EXCLUDE.match(ref):
                left[WHY[re.match(r'[A-Z]+', ref).group(0)]].append(ref); continue
            m = lcsc.get((r['Value'], r['Footprint']))
            if m is None:
                missing.append('%s (%s, %s)' % (ref, r['Value'], r['Footprint'])); continue
            # one BOM line per LCSC part: 10k and 10k/1% are the same reel
            g = groups.setdefault((m['LCSC'], m['Package']), {'vals': [], 'refs': []})
            if r['Value'] not in g['vals']:
                g['vals'].append(r['Value'])
            g['refs'].append(ref)
    if missing:
        sys.exit('no LCSC number in fab/jlc_lcsc.csv for: ' + ', '.join(missing))
    key = lambda s: (re.match(r'[A-Z]+', s).group(0), int(re.search(r'\d+', s).group(0)))
    bom = os.path.join(out, name + '_BOM_JLC.csv')
    jlc_refs = set(); part_of = {}
    with open(bom, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (part, pkg), g in sorted(groups.items(), key=lambda kv: key(sorted(kv[1]['refs'], key=key)[0])):
            refs = sorted(g['refs'], key=key); jlc_refs |= set(refs)
            part_of.update((r, part) for r in refs)
            val = COMMENT.get(part) or max(g['vals'], key=len)        # '10k/1%' rather than '10k'
            w.writerow([val, ','.join(refs), pkg, part])
            rep.append('   %-24s %-11s %-9s %3d  %s' % (val, pkg, part, len(refs), ','.join(refs)))
    rep.insert(len(rep) - len(groups), 'BOM: %d lines, %d parts' % (len(groups), len(jlc_refs)))

    # ---- CPL (only what JLC places)
    pos_raw = os.path.join(out, 'pos_raw.csv')
    run([CLI, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp', '-o', pos_raw, PCB])
    cpl = os.path.join(out, name + '_CPL_JLC.csv')
    seen = set()
    with open(cpl, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in csv.DictReader(open(pos_raw, encoding='utf-8')):
            if r['Ref'] not in jlc_refs:
                continue
            side = 'Top' if r['Side'].lower().startswith('top') else 'Bottom'
            w.writerow([r['Ref'], '%.4fmm' % float(r['PosX']), '%.4fmm' % float(r['PosY']), side, '%g' % ((float(r['Rot']) + ROT.get(part_of[r['Ref']], 0)) % 360)])
            seen.add(r['Ref'])
    if seen != jlc_refs:
        sys.exit('CPL and BOM disagree: %s' % sorted(seen ^ jlc_refs))
    rep.append('CPL: %d placements, sides %s' % (len(seen), 'top only'))
    rep.append('Not assembled by JLC:')
    for why, refs in left.items():
        rep.append('   %-45s %s' % (why, ','.join(sorted(refs, key=key))))
    rep.append('DNP (not fitted): see schematic NA(...) values')
    glob_ = [k for k, g in groups.items() if not k[0]]
    if glob_:
        rep.append('GLOBAL SOURCING (no LCSC stock): ' + '; '.join('%s %s' % (', '.join(groups[k]['refs']), max(groups[k]['vals'], key=len)) for k in glob_)
                   + ' - in the JLC BOM step pick the part from Global Sourcing (DigiKey/Mouser).')
    if ROT:
        rep.append('Rotation offsets applied: ' + ', '.join('%s %+d' % (k, v) for k, v in ROT.items()))
    rep.append('CHECK in the JLC placement preview: U1 (LP5907) magenta pin 1 on the top-left pad (silk dot). '
               'CON1/CON2 (TFM, unshrouded, no pegs) are symmetric: only the centring matters.')
    open(os.path.join(out, 'pack_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    for f in ('drc.json', 'bom_raw.csv', 'pos_raw.csv'):
        os.remove(os.path.join(out, f))
    print('\n'.join(rep))
    print('pack:', out)


if __name__ == '__main__':
    main()

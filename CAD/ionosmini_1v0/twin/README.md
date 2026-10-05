# PCB Digital Twin — ionos-sdr-mini

Gyártás előtti verifikációs eszköz. Nem rajzol, nem szimulál RF-et, nem
helyettesíti a DRC-t: **azt bizonyítja, hogy a bekötés az, aminek hittük.**

A mumus a félrekötés. Egy elcsúszott csatlakozóláb, egy felcserélt jelpár,
egy olyan lábra tett jel, amit a rádió board alatt már más hajt — ezek a
hibák ERC-vel és DRC-vel **nem** derülnek ki, mert mindkettő csak a saját
rajzunkkal önkonzisztens. A twin azért éri meg, mert **két egymástól
független leírást ütköztet**, és bármelyik kettő közti eltérés hibát jelent.

```
   forrásdokumentumok                     a saját rajzunk
   (Silabs séma, adatlapok)               (KiCad .kicad_sch)
            |                                     |
            v                                     v
     spec_signals.py                        netlist.net
     spec_radioboard.py   <--- ÜTKÖZTETÉS --->  (kicad-cli export)
            |                                     |
            +------------- twin_check.py ---------+   1. réteg
            +------------- twin_plug.py  ---------+   2. réteg
```

---

## Mi van a mappában

| fájl | mi ez |
|---|---|
| `spec_signals.py` | **A hordozó specifikációja.** A forrásdokumentumokból írva, nem a sémából: mezzanine lábkiosztás, a 14 jel, vágási pontok, ESP32-S3 lábkorlátok, kijelző-lábkiosztás, gomblétrák. |
| `spec_radioboard.py` | **A rádió board modellje.** A BRD4265B-A01 séma alapján: mind a 80 mezzanine láb, a WSTK hálók, az EFR32 port-lábak, a soros elemek, ki hajt mit. |
| `twin_check.py` | **1. réteg** — a netlista a saját specifikációval szemben. |
| `twin_plug.py` | **2. réteg** — bedugjuk a rádió boardot, és végigkövetjük a jelutat. Öntesztet is tartalmaz. |
| `netlist.net` | a KiCad által exportált netlista (generált, verziókövethető) |
| `erc.rpt`, `drc.rpt` | a `kicad-cli` jelentései (generáltak) |

---

## Használat

```powershell
cd C:\Users\RF\Documents\GitHub\ionos-sdr-mini\CAD\ionosmini_1v0

# 0. netlista frissítése a sémából  (MINDIG ezzel kezdd)
& "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export netlist `
    --format kicadsexpr --output twin\netlist.net ionosSDR_mini.kicad_sch

# 1. réteg
& "C:\Program Files\KiCad\10.0\bin\python.exe" twin\twin_check.py

# 2. réteg
& "C:\Program Files\KiCad\10.0\bin\python.exe" twin\twin_plug.py

# 2. réteg röviden + önteszt
& "C:\Program Files\KiCad\10.0\bin\python.exe" twin\twin_plug.py -q --selftest
```

Kilépési kód: `0` = tiszta, `1` = van FAIL, `2` = nincs netlista,
`3` = az önteszt elbukott (magának az eszköznek a hibája).

A KiCad saját Pythonját használjuk, mert az biztosan ott van a gépen —
a twin maga **semmilyen külső csomagot nem igényel**, sima Python 3 is jó.

---

## 1. réteg — `twin_check.py`

A netlistát a `spec_signals.py`-vel veti össze. Amit vizsgál:

- **signal** — minden jel útja az ESP32 lábtól a csatlakozó lábig, BFS-sel
  végigkövetve a soros 0 Ω-okon és a jumpereken keresztül. Nem névegyezést
  néz: a soros elem után a háló neve megváltozik, a réz nem.
- **power** — a mezzanine fix táp- és földlábai.
- **cut** — jelenként pontosan egy vágási pont (R1–R5, R8, JP1–JP8).
- **esp32** — tiltott GPIO-k (oktális PSRAM 33–37, flash 26–32, natív USB
  19/20), strapping lábak, az SPI2 IO_MUX készlet, ADC1 csatornák.
- **tft** — a DISP2 lábai az ER-TFTM024-3 adatlapja ellen.
- **net** — egypontos hálók, több hajtó egy hálón.
- **ladder** — a gomblétrák ADC-szintjei és az RC beállási ideje analitikusan.

## 2. réteg — `twin_plug.py`

Itt dugjuk be a rádió boardot. A hordozó netlistája és a
`spec_radioboard.py` a 80 mezzanine lábnál **egyetlen villamos gráffá**
olvad össze, union-find-dal. Ezen fut:

- **intent** — statikus követés: minden jel a szándékolt EFR32 port-lábon
  kell hogy kijöjjön. Ha nem, a riport megmondja, hol jön ki helyette.
- **down / up** — **jelsétáltatás**. Egy darab `1`-est végigléptetünk a
  jeleken (a többit közben `0`-ra hajtjuk), és megnézzük, melyik lábon
  bukkan föl. Ez azért jobb a puszta netlista-olvasásnál, mert egy felcserélt
  jelpárnál a vett minta **permutáció** lesz, és a twin meg tudja mondani,
  *melyik jel ment hova*. Két irányban fut, mert a linken a **FG23 az SPI
  mester**: SCLK / MOSI / CS a FG23 kimenete, RDY és CMD az ESP32-é.
- **socket** — minden lábra, amit megfogunk, kiírja, mi van alatta.
- **alias** — *ez a legfontosabb.* A BRD4265B több jelet **két vagy három
  mezzanine lábra is kivezet** (lásd lentebb). Ha egy ilyen „másik" lábra
  bármit rákötnénk, az a panel alatt rövidzár, és semmilyen DRC nem veszi
  észre. A twin minden ilyen lábat felsorol, és ellenőrzi, hogy üresen marad.
- **dir** — ki hajtja a jelet a két oldalon. Ha mindkét oldal „in", senki.
- **power** — táplábak, és amit szándékosan üresen hagyunk (5V, USB).

### Az absztrakt ESP32

Szándékosan buta: egy láb vagy `0`-t hajt, vagy `1`-et, vagy nagyimpedanciás.
A chipet emulálni lehetetlen és fölösleges — a félrekötés a cél. Ugyanígy a
villamos modell: a hálók ideális rövidzárak, a soros 0 Ω-ok és a bezárt
jumperek vezetnek, a felhúzók, létraellenállások és kondenzátorok **nem**
(ha azokat is rövidzárnak vennénk, valódi hibákat rejtenénk el).

### Önteszt

```
twin_plug.py --selftest
```

Négy szándékos hibát injektál a netlista egy másolatába, és megköveteli,
hogy a twin mind a négyet elkapja:

| injektált hiba | amit a twin mond |
|---|---|
| két jel felcserélve a foglalaton | `FG23_CMD should reach PA06, it reaches PA07` |
| egy jel egy lábbal elcsúszva | `FG23_SCLK should reach PC05, it reaches PA04` |
| élő jel egy üresen hagyandó lábra kötve | `FG23_CMD reaches PA06 but ALSO PA03` |
| jel olyan lábra, amit a rádió board nem köt | `FG23_RDY ... it reaches nothing on the radio board` |

**Egy verifikációs eszköz, amit még soha senki nem látott megbukni, nem
megbízható.** Ezért van ez benne, és ezért kell minden bővítés után lefuttatni.

---

## Amit a rádió board oldaláról kiderítettünk

Mindegyik a BRD4265B-A01 sémájából olvasva, és a PcbDoc hálólistájával
keresztellenőrizve. A `spec_radioboard.py` fejléce hivatkozza a lapokat.

### A mezzanine kiosztás (P200 → CON1, P201 → CON2)

| P200 | | P201 | |
|---|---|---|---|
| 1 | 3V3 (mi tápláljuk) | 1 | GND |
| 2 | GND | 2 | VMCU_IN (mi tápláljuk, R201 0 Ω → VMCU) |
| 3–12 | WSTK_P36…P45 | 3–38 | WSTK_P0…P35 |
| 13–34 | WSTK_F0…F21 | 39 | GND |
| 35 | 5V | 40 | NC (a sémán X-szel jelölve) |
| 36 | USB_VREG (a board hajtja!) | | |
| 37 | USB_VBUS | | |
| 38 | GND | | |
| 39 | BOARD_ID_SCL | | |
| 40 | BOARD_ID_SDA | | |

### A mi 14 jelünk útja, végig

| jel | ESP32 | CONx láb | WSTK | EFR32 port | QFN48 láb |
|---|---|---|---|---|---|
| FG23_SCLK | GPIO12 | CON2.15 | WSTK_P12 | **PC05** | 6 |
| FG23_MOSI | GPIO11 | CON2.10 | WSTK_P7 | **PC00** | 1 |
| FG23_CS | GPIO10 | CON2.13 | WSTK_P10 | **PA07** | 32 |
| FG23_CMD | GPIO13 | CON2.11 | WSTK_P8 | **PA06** | 31 |
| FG23_RDY | GPIO14 | CON2.9 | WSTK_P6 → **R216 0 Ω** | **PD02** | 46 |
| FG23_SPARE | — | CON2.7 | WSTK_P4 | **PA05** | 30 |
| SWDIO | GPIO38 | CON2.21 | WSTK_P18 | **PA02** | 27 |
| SWCLK | GPIO39 | CON2.23 | WSTK_P20 | **PA01** | 26 |
| SWO | GPIO48 | CON2.19 | WSTK_P16 | **PA03** | 28 |
| RESETn | GPIO40 | CON1.17 | WSTK_F4 | **RESETn** | 13 |
| I2C_SCL | GPIO42 | CON1.39 | BOARD_ID_SCL | M24C02 EEPROM | — |
| I2C_SDA | GPIO41 | CON1.40 | BOARD_ID_SDA | M24C02 EEPROM | — |
| 3V3_RADIO | — | CON1.1 | 3V3 | a board 3,3 V sínje | — |
| VMCU_IN | — | CON2.2 | VMCU_IN | R201 0 Ω → VMCU | — |

### ★ A csapda: ugyanaz a port-láb több mezzanine lábon ★

A BRD4265B a debug- és trace-jeleket **többszörösen kivezeti**. Az alábbi
lábaknak **üresen kell maradniuk**, különben a rádió board alatt rövidzár
keletkezik, amit se az ERC, se a DRC nem lát:

| EFR32 port | a mi jelünk | és ezek a lábak is ugyanaz a csomópont |
|---|---|---|
| PA01 | SWCLK | CON1.14 (WSTK_F1) |
| PA02 | SWDIO | CON1.13 (WSTK_F0) |
| PA03 | SWO | CON1.9 (WSTK_P42, trace) **és** CON1.15 (WSTK_F2) |
| PA05 | FG23_SPARE | CON1.10 (WSTK_P43, trace) |
| PA06 | FG23_CMD | CON1.11 (WSTK_P44, trace) |
| PA07 | FG23_CS | CON1.12 (WSTK_P45, trace) |
| PD02 | FG23_RDY | CON1.3 (WSTK_P36, de ott R217 **nincs beültetve**) |

A trace-leágazásokat a séma geometriájából olvastuk (junction-pontok
pixelpontos helye), majd a PcbDoc hálónevein ellenőriztük: a PA06 egyesített
hálójának neve valóban `WSTK_P44`, a PA05-é `WSTK_P4`, a PA07-é `WSTK_P10` —
pontosan amit a leágazások megjósolnak.

**A jelen állapot tiszta: mind a hét láb üres a hordozón.** A twin ezt
minden futásnál újraellenőrzi, tehát egy jövőbeli módosítás nem tudja
észrevétlenül elrontani.

### Egyéb megállapítások

- **R216 0 Ω be van ültetve, R217 nincs** (BOM). Ezért megy a FG23_RDY a
  PD02-re, és ezért nem él a WSTK_P36 (JOYSTICK) ág.
- **RESETn-en a rádió boardon nincs külső felhúzó** — csak az EFR32 belső
  felhúzója tartja. Az ESP32 boot alatt a GPIO40 nagyimpedanciás, tehát a
  FG23 nem marad resetben. Push-pull hajtás esetén ügyelni kell rá, hogy a
  firmware ne hagyja lenn.
- **A BOARD_ID EEPROM-nak a rádió boardon van 10 kΩ felhúzója** (R200) →
  a hordozón R26/R27 helyesen DNP.
- **USB_VREG a rádió board kimenete** (CON1.36) — soha nem szabad hajtani.
- A P200/P201 a rádió boardon **WCON 2344-220MS3CUNR6 foglalat**, tehát a
  hordozóra tüske (terminal) való — ezt a `TFC-120-02-XX-D-A-K-TR` rendelési
  kódnál a gyártás előtt még fizikailag igazolni kell.

---

## Mit NEM tud a twin

Őszintén, hogy senki ne bízzon benne jobban, mint amennyit ér:

- **Nem lát rézt.** A netlistából dolgozik, nem a `.kicad_pcb`-ből. Ha a
  layout eltér a sémától, azt a `kicad-cli pcb drc --schematic-parity` fogja
  meg, nem ez (lásd lentebb).
- **Nem ismeri a valódi elektromos szinteket.** Nincs benne meredekség,
  terhelés, áthallás, reflexió. Ez a 3. réteg dolga lesz.
- **Nem tudja, hogy a rádió boardot melyik irányba dugod be.** A foglalat
  1-es lábának oldalát a sémából nem lehetett lezárni → ezt
  **fizikailag kell igazolni** (lásd a bemérési listát).
- **A rádió board modellje emberi olvasat.** Ha a Silabs kiad egy A02-t,
  a `spec_radioboard.py`-t frissíteni kell.

---

## Gyártás előtti fizikai ellenőrző lista

Amit a twin elvből nem tud eldönteni, és kézzel kell:

1. **A foglalat 1-es lábának oldala.** A beültetett rádió boardon
   folytonosság a CON1 1-es pad és a P200 1-es lábának 3V3-ja között.
   (A `MEZZ_ROT = 180.0` paraméter ettől függ.)
2. **SFC vagy SFM család?** A rádió boardon WCON foglalat van; a hordozóra
   rendelt Samtec tüske érintkezőanyagát és áramterhelését egyeztetni.
3. **A TFC footprint `(attr through_hole)` → `smd`** a `.kicad_mod`-ban.
4. **`N8R2` → `N16R8`** az IC1 szimbólum/footprint nevében (kozmetikai,
   de a BOM-ba így megy ki).
5. **R1–R5 jelenleg 0 Ω.** Soros csillapításhoz 22–33 Ω javasolt, ha a
   SPI_HZ-et emeljük.
6. Az ER-TFTM024-3 szimbólumba **beágyazott 2,78 MB-os PDF** kiszedése.

---

## Mit ad hozzá a `kicad-cli`

A twin mellé, nem helyette:

```powershell
# ERC
kicad-cli sch erc --output twin\erc.rpt --severity-error --severity-warning `
    --exit-code-violations ionosSDR_mini.kicad_sch

# DRC + séma/layout paritás  (ez utóbbi a lényeg)
kicad-cli pcb drc --output twin\drc.rpt --schematic-parity `
    --severity-error --severity-warning --exit-code-violations `
    ionosSDR_mini.kicad_pcb
```

A `--schematic-parity` az, amit a twin nem csinál: összeveti a layout
footprintjeit és hálóit a sémával. Ez találta meg, hogy a generált panelen
a footprintek könyvtárelőtag nélkül (`CAPC1005X60_0402` a
`rpw_lib:CAPC1005X60_0402` helyett) szerepeltek, és hogy 282 szimbólum-mező
hiányzott a footprintekről — mára mind javítva.

További rétegnek érdemes még megnézni (egyik sincs telepítve):
`KiBot` (CI-ba fogható gyártási futószalag, beleértve az ERC/DRC-t),
`InteractiveHtmlBOM` (ültetési ellenőrzés), `kicad-diff` (verziók közti
vizuális diff).

---

## Átvitel másik projektbe

A twin szándékosan két részre van bontva:

**Projektfüggetlen (vihető, ahogy van):**
- a netlista-olvasó és a gráf (`twin_check.py` `sexp` / `load` /
  `build_graph` / `path`, `twin_plug.py` `Stack` / `Esp32` / `_walk`)
- az önteszt-keret (`FAULTS`, `selftest`)
- a riportolás (`say` / csoportok / kilépési kódok)

**Projektfüggő (újraírandó):**
- `spec_signals.py` és `spec_radioboard.py` — ezek a *specifikációk*.

A módszer lényege, és amit érdemes átvinni: **a specifikációt a
forrásdokumentumokból írd meg, soha ne a sémából.** Ha a sémából írod,
a twin azt bizonyítja, hogy a séma egyezik önmagával — ami semmit nem ér.
Minden spec-sor mellé írd oda, melyik dokumentum melyik lapjáról jött.

A gyakorlati menet egy új panelnél:

1. `spec_*.py` megírása a gyártói sémából/adatlapokból, forráshivatkozásokkal.
2. Netlista export, 1. réteg lefuttatása → a saját rajz önkonzisztens.
3. A másik oldal modellje, 2. réteg → bedugva is stimmel.
4. Önteszt bővítése az adott panel tipikus hibáival.
5. ERC + DRC `--schematic-parity`.
6. A fizikai ellenőrző lista, amit a modell elvből nem tud eldönteni.

---

## Állapot (2026-10-05)

```
1. réteg (twin_check.py)   66 pass,  6 warn, 0 FAIL
2. réteg (twin_plug.py)    70 pass,  1 warn, 0 FAIL
önteszt                    mind a 4 szándékos hiba elkapva
kicad-cli sch erc           0 hiba, 48 figyelmeztetés
kicad-cli pcb drc           0 szabálysértés, 0 paritásprobléma,
                            7 kapcsolat nélküli elem (mind zone-sziget)
```

A figyelmeztetések értelmezése: a 2. rétegben az egyetlen WARN a FG23_SPARE,
ami szándékosan csak mérőpontig megy. Az 1. rétegben 4 egypontos
dokumentációs címke és 2 megjegyzés a 3,3 V-os üresjárati szintről, ami a
3,1 V-os ADC-végkitérést levágja — ez a „nincs gomb" detektáláshoz rendben van.

---

# 4. réteg — mechanikai (`twin_mech.py`)

Az 1–3. réteg hálózatot olvas. **Ez a réteg a NYÁK-ot olvassa**, és azt a
kérdést teszi fel, amit rézkapcsolatból nem lehet megválaszolni:

> Ha a rádió boardot ráültetem az illesztőtüskékre, a **mi n-edik lábunk**
> tényleg az **ő n-edik lábukat** éri-e — vagy a footprint meg van fordítva?

**Ez a réteg talált egy kritikus hibát:** a CON1/CON2 180°-kal el volt
forgatva, a mi n-edik lábunk a rádió board 41−n lábára ült. A padok
geometriailag tökéletesen fedésben voltak, csak a **számozás** fordult meg —
ezért se az ERC, se a DRC, se az 1–2. réteg nem vette észre. A 3V3_RADIO a
BOARD_ID_SDA-ra, a VMCU_IN pedig a GND-re ment volna.

## Mit vizsgál

| csoport | mit |
|---|---|
| `fit` | az illesztőfuratok osztása a gyári ±13,651 mm-rel; a mating transzformáció levezetése |
| `pins` | **mind a 80 láb** — a mi lábunk a saját számát éri-e |
| `outline` | a 30×45-ös panel ráfér-e a hordozóra, hol lesz az SMA |
| `clearance` | mi van alatta a mi oldalunkon, és elfér-e (6,35 mm mated − 1,10 mm az ő alsó oldaluk = **5,25 mm**) |
| `devkit` | a DevKit fejléc-geometriája és a modul burkolata |
| `hygiene` | van-e courtyard és szitarajz minden footprinten |
| `overlay` | „lakmuszpapír" SVG mindkét illesztésről |

## A lakmuszpapír

A `twin/mech/` alá két SVG kerül, böngészőben megnyitható:

- `overlay_radioboard.svg` — a BRD4265B foglalatai (piros) és a mi tüskéink
  (kék) **azonos léptéken, félig áttetszően**, az illesztőfuratokra horgonyozva.
- `overlay_devkit.svg` — a DevKit fejléce, a footprint burkolata (zöld) és a
  külső forrásokból vett 28×70 mm (narancs szaggatott) a panelünk élével.

A rádió boardnál a geometria **akkor is fedésben van, ha a számozás fordított** —
ezért a számokat a `pins` vizsgálat dönti el, nem a szem. A lakmuszpapír arra
jó, amire való: elcsúszás, méretkülönbség, lelógás.

## A forrásadatok, ahonnan a mechanika jön

Mind a gyári gerberekből, nem következtetésből:

| mi | érték | forrás |
|---|---|---|
| panelméret | 30,000 × 45,000 mm, R1,2 sarok | `.GM1` |
| illesztőfuratok | 4× Ø1,349 NPTH, (1,349 / 28,651) × (5,001 / 28,999) | `.DRL` |
| csatlakozó-középvonalak | y = 5,000 és 29,000 → **24,000 mm** | `.DRL` + `.GBL` |
| pad-raszter | 1,27 mm, 20 oszlop, u = 2,935…27,065, sorok ±1,45 | `.GBL` |
| pad-méret | 0,74 × 2,00 mm | `.GBL` apertúra |
| **1-es láb** | **a kis u-s végen, a középvonal alatti sorban** | `.GBO` szita + `.GBL` rézmintázat |
| SMA | Ø1,501 középtű (25,601, 38,600) + 4× Ø1,6 poszt 5,08 mm négyzeten | `.DRL` |
| alsó oldali alkatrészek | 2 foglalat, U200 SOIC-8, RP200, 20 mérőpad, néhány 0402 | assy rajz, 2. lap |

Az 1-es láb oldala a legfontosabb és a legnehezebb: a szitán mindkét
csatlakozónál a „40" van a nagy u-s végen, és ezt **a P201 mind a 40 padjának
réz-rajta/nincs-rajta mintázata is megerősíti** — az a 40 bites minta csak
ebben az egy orientációban egyezik a ismert bekötéssel.

## Nyitott mechanikai kérdések

1. **DISP1-nek nincs courtyardja** (csak a 4 lábú fejléc). A modul testét az
   adatlapból kell megrajzolni, **a könyvtárban, nem a példányon** — a
   példányra rajzolás örök „eltér a könyvtártól" figyelmeztetést csinál,
   ami később elrejt egy valódi eltérést.
2. **A DevKit burkolata ellenőrizetlen.** A footprint 26,42 × 62,74 mm-t mond,
   külső források 28 × 70 mm-t. Ha a 70 mm az igaz, a modul **1,35 mm-rel
   lelóg a felső élünkről**. Espressif `DXF_ESP32-S3-DevKitC-1_V1.1_20220429`
   kell hozzá; nem töltöttem le.
3. **Nincs a panelen semmi, ami jelezné a rádió board irányát.** Az
   illesztőtüskék szimmetrikusak, tehát fizikailag megfordítva is bedugható —
   és fordítva a P201 ülne a CON1-re. Kell egy szitarajz-körvonal + irányjel.
4. A mérőpontoknak és néhány 0402-nek nincs szitateste (elfogadható).

---

## Állapot (2026-10-05, a javítás után)

```
1. réteg (twin_check.py)   66 pass,  6 warn, 0 FAIL
2. réteg (twin_plug.py)    70 pass,  1 warn, 0 FAIL   (önteszt: 4/4 elkapva)
4. réteg (twin_mech.py)    15 pass,  3 warn, 1 FAIL   (DISP1 courtyard)
kicad-cli sch erc           0 hiba, 48 figyelmeztetés
kicad-cli pcb drc           0 szabálysértés, 0 paritásprobléma,
                            7 kapcsolat nélküli elem (mind zone-sziget)
panel                       4683 mm vezeték, 172 via (90 huzalozás + 82 tűzés)
```

---

# 3. réteg — analóg (`twin_analog.py`)

Az 1., 2. és 4. réteg azt kérdezi, hogy *össze van-e kötve* és *elfér-e*.
Ez azt, hogy **túléli-e a jel az utat** — és a **valódi, megrajzolt
vezetékhosszakkal** dolgozik, amiket a `.kicad_pcb`-ből olvas ki, nem
becslésből.

**Nem kell semmit telepíteni:** a KiCad-del szállított `ngspice.dll`-t
hajtjuk ctypes-on keresztül (`twin/ngspice.py`). Minden deck kiíródik a
`twin/spice/*.cir` alá is, tehát QucsStudióban vagy a KiCad saját
szimulátorában kézzel is piszkálható.

## Mit vizsgál

| csoport | mit |
|---|---|
| `line` | a 0,25 mm-es vezeték mint tápvonal: Z0 és terjedési idő a rétegrendből |
| `spi` | az FG23-link 4 MHz-en és a 30 MHz-es NYÁK-célon, R1–R5 sorozatellenállás-söpréssel |
| `i2c` | a BOARD_ID busz felfutása a valódi hosszból és eszközkapacitásból |
| `ladder` | a gomblétrák szintjei és beállása az ADC-n |
| `ldo` | a 3V3_RADIO sín terhelésugrásra, plusz a réz IR-esése |

## ★ A fontos eredmény: R1–R5 = 22 Ω ★

A 0,25 mm-es vezeték a 0,2104 mm-es prepreg fölött **Z0 = 61,2 Ω, 5,9 ps/mm**.
A leghosszabb link (FG23_SCLK, 161 mm) egyirányú késleltetése 958 ps — a
30 MHz-es cél 33 ns-os periódusához képest ez **villamosan hosszú vonal**.

```
FG23_SCLK @30 MHz   0R: 12,60 %   22R: 0,00 %   33R: 0,00 %   47R: 0,00 %
FG23_MOSI @30 MHz   0R: 11,41 %   22R: 0,00 %   ...
FG23_CS   @30 MHz   0R: 12,07 %   22R: 0,00 %   ...
FG23_CMD  @30 MHz   0R:  7,39 %   22R: 0,00 %   ...
FG23_RDY  @30 MHz   0R:  6,34 %   22R: 0,00 %   ...
```

(csúcs-eltérés a VDD százalékában)

**0 Ω-mal 6–13 % túl-/alullövés**, 22 Ω-mal gyakorlatilag nulla. A FG23 saját
~45 Ω-os kimenete + 22 Ω = 67 Ω, ami a 61 Ω-os vonalhoz jól illesztett.
**Már a mai 4 MHz-en is érdemes beültetni**, a 30 MHz-es célon kötelező.

## A többi eredmény

- **I2C:** 196 mm réz + 3 eszköz → **50 pF**, 4,7 kΩ felhúzóval **200 ns**
  felfutás. Fér a 400 kHz-es 300 ns-os határba (és bőven a 100 kHz-esbe).
- **Gomblétrák:** 0,595 V a legkisebb lépcső, az ADC 12 bites LSB-je 0,8 mV —
  bőven elég.
- **LDO:** 50 mA-es terhelésugrásra **46 mV letörés**, 37 mV túllövés
  (1,2 µF kimeneti kapacitással). Rendben.
- **IR-esés:** a 3V3_RADIO + VMCU_IN útvonal 275 mm 0,25 mm-es rézen →
  549 mΩ → **27,5 mV 50 mA-nél**. Elfogadható, de ha akarod, 0,45 mm-re
  szélesíthető.

## Amire figyelni kell

**A rétegrend feltételezés.** A `.kicad_pcb`-ben nincs stackup blokk, ezért
egy szokásos 1,6 mm-es négyrétegű felépítést veszünk (0,2104 prepreg / 1,065
core / 0,2104 prepreg, εr 4,3). **Az impedancia- és felfutásszámok csak
annyit érnek, amennyit ez a feltételezés.** A gyártótól kell a tényleges
rétegrend, és akkor a `spec_analog.STACKUP`-ot frissíteni.

A driverek egyszerű Thévenin-modellek (45 Ω / 40 Ω forrásellenállás, 2 ns
él), nem IBIS. A cél itt is az arány, nem az abszolút pontosság: 0 Ω vs 22 Ω
különbsége robusztus, a 12,6 % harmadik tizedesjegye nem.

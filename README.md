# Ionos SDR mini

![Ionos SDR mini](docs/img/banner.png)

Simplified, low-cost sibling of [Ionos SDR](https://github.com/ionos-sdr/ionos-sdr): a carrier PCB that turns a stock Silicon Labs radio board into a usable SDR. An ESP32-S3 DevKitC sits on female headers on the left, a Silicon Labs radio board plugs into the mezzanine socket on the right, and both displays are optional. No custom RF design, no exotic parts — the radio board you already have in a drawer does the RF.

![Ionos SDR mini rev-B3 3D render: ESP32-S3 DevKitC, 0.96 inch OLED, BACK/OK keys, 2.4 inch ER-TFTM024-3 TFT, cursor keys and the mezzanine sockets for the radio board](docs/img/ionos-sdr-mini_revB3_3d.png)

*rev-B3 (KiCad 3D render): DevKitC on headers, SSD1306 OLED with BACK/OK below it, the optional ER-TFTM024-3 TFT on a 2x20 socket in the middle (manufacturer's 3D model), cursor keys and the radio board sockets on the right. Shown: the 4-layer variant, where the top layer is GND copper only and signals run on In1 and B.Cu.*

**Status: hardware design in progress.** The firmware and the measured facts live in the [main repository](https://github.com/ionos-sdr/ionos-sdr); this repo holds the carrier board and its documentation.

## What it is

- **Carrier only.** 168 x 80 mm, four M3 nylon standoffs. Two variants: 4-layer (`layout/rev-b3`, JLC04161H-7628: F.Cu GND / In1 signal / In2 GND + power / B.Cu signal) and this 2-layer one (`layout/rev-b3-2l`, 1.6 mm FR-4, GND pour and tracks on both layers; fit R1–R5 = 82 Ω here (twin_analog on the v2 routing; 22 Ω on the 4-layer board)). No RF layout risk: matching network, SMA and shielding stay on the Silicon Labs radio board.
- **Any radio board fits.** The mezzanine pair is the standard WSTK radio board interface, so BRD4265B (FG23, 434 MHz, 10 dBm) is only the first panel. The pin-to-signal mapping differs per panel and is selected in firmware.
- **Panel auto-detect.** The radio board's M24C02 board-ID EEPROM sits on the same I2C bus as the OLED, so the firmware can read which panel is plugged in and load the matching pin map at boot.
- **Bootstrap flashing.** SWDIO, SWCLK, SWO and RESET are routed to the ESP32, which bit-bangs SWD. A blank radio board can be programmed with nothing but this board and a USB cable; routine updates then go over the UART command link.
- **One cable.** Power and data over the DevKit's USB-C. The radio gets its own low-noise LDO from the 5 V rail, not the DevKit's shared 3.3 V.

## Architecture

![System architecture: Silicon Labs radio board on a mezzanine socket, ESP32-S3 DevKitC carrier with LDO, buttons, optional TFT and OLED, USB or WiFi to the host](docs/img/architecture-diagram.svg)

- **RX**: FG23 I/Q capture and server-side FFT lines over SPI2 (IO_MUX) to the ESP32-S3, then to the host or to the on-board display.
- **Control**: RDY handshake and a UART command link; SWD is bit-banged by the ESP32 so a blank panel can be programmed with nothing but this board.
- **Power**: a single low-noise LDO feeds VMCU_IN; the radio board's own DC-DC handles PAVDD, so one supply pin powers the whole panel.

## Hardware

| Block | Part | Notes |
| --- | --- | --- |
| MCU | ESP32-S3-DevKitC-1, N16R8 | On 2x22 female headers, antenna end overhanging the board edge |
| Radio | Silicon Labs radio board | 2x 2x20, 1.27 mm mezzanine, 24 mm apart; BRD4265B validated first |
| Display (optional) | EastRising ER-TFTM024-3, 2.4", ILI9341 | 240x320, TE pin wired for tear-free hardware scroll; resistive or capacitive touch |
| Display (optional) | SSD1306 0.96" OLED, I2C | Status line when the large display is not fitted |
| Buttons | 6+1 tactile, C&K PTS647 | UP/DOWN/LEFT/RIGHT plus BACK/OK, a seventh SPARE footprint (key optional); two resistor ladders |
| Radio supply | LP5907-3.3 or TPS7A2033 | ~6.5 uVrms, fed from the DevKit 5 V rail, ferrite + 10 uF at the connector |

Seven keys cost two pins, not seven: both ladders use the same 10 k pull-up and the same 0 R / 2.2 k / 6.8 k / 22 k set to GND (UP/DOWN/LEFT/RIGHT on GPIO2, BACK/OK/SPARE on GPIO1, the 22 k level of that ladder left free), read on ADC1 with a 1 k + 100 nF filter at the pin. One threshold table serves both: 0.30 / 0.97 / 1.80 / 2.79 V. Only the 0 R keys (UP, BACK) can wake the chip from deep sleep. The freed GPIOs carry the SWD lines.

## Pin mapping (BRD4265B)

The EXP header numbers come from the Silicon Labs radio board documentation; the connector pins are what you actually route. For EXP 3 to 16 the P201 pin number equals the EXP number.

| Signal | ESP32-S3 GPIO | FG23 pin | WSTK net | Connector pin |
| --- | --- | --- | --- | --- |
| SCLK | 12 (SPI2 IO_MUX) | PC05 | WSTK_P12 | P201-15 |
| MOSI | 11 (SPI2 IO_MUX) | PC00 | WSTK_P7 | P201-10 |
| CS | 10 (SPI2 IO_MUX) | PA07 | WSTK_P10 | P201-13 |
| RDY | 14 | PD02 | WSTK_P6 | P201-9 |
| CMD | 13 (UART TX) | PA06 | WSTK_P8 | P201-11 |
| SWDIO | 38 | PA02 | WSTK_P18 | P201-21 |
| SWCLK | 39 | PA01 | WSTK_P20 | P201-23 |
| SWO | 48 | PA03 | WSTK_P16 | P201-19 |
| RESETn | 40 | RESETn | WSTK_F4 | P200-17 |
| BOARD_ID_SDA / SCL | 41 / 42 (I2C0) | - | BOARD_ID | P200-40 / P200-39 |
| VMCU_IN | - | - | VMCU_IN | P201-2 |
| 3V3 | - | - | 3V3 | P200-1 |
| GND | - | - | GND | P200-2, 38; P201-1, 39 |

The FG23 link runs on SPI2 through the IO_MUX pins so the slave interface keeps its headroom for higher clocks; the optional TFT is on SPI3. `VRF` is unused on BRD4265B and the on-board DC-DC feeds PAVDD, so a single supply pin powers the whole panel; P201-40 (VRF_IN) only runs to test point TP8, and P200-37 (5 V) has a not-fitted 0 R (R33) from the DevKit 5 V for panels that need it.

## Display and touch

The ER-TFTM024-3 sits on SPI3 (SCK 4, MOSI 5, MISO 6, CS 7, D/C 15, RST 16, BL 17, TE 18). Its resistive touch controller (XPT2046) and the module's optional SD/font/flash chips share a second header bus (pins 32/33/34), which is tied to the TFT bus on the carrier; the touch transactions run at their own ~2 MHz clock. 10 k pull-ups hold the module's SD/FONT/FLASH chip selects (header 35/36/37) inactive so nothing else drives MISO.

| Pin | Resistive (XPT2046) | Capacitive (I2C CTP) |
| --- | --- | --- |
| TCH_A, GPIO8, header 30 | SPI CS | I2C SCL |
| TCH_B, GPIO21, header 31 | PENIRQ | I2C SDA |
| TCH_INT, GPIO9, header 39 | unused | CTP INT |

Both 4.7 k pull-ups (TCH_A, TCH_B) are fitted in every build, so one BOM serves both panel types; firmware picks the mode. **Before the first power-up**, measure the panel's MISO/TE high level with VDD = 5 V: if it follows 5 V, run the panel from 3V3 or add level shifting.

## DevKit: clone or official

The carrier is laid out for the AliExpress ESP32-S3 DevKit clone, whose RGB LED is on GPIO47. On official Espressif ESP32-S3-DevKitC-1 boards the WS2812 sits on GPIO38 (v1.1) or GPIO48 (v1.0), which are SWDIO and SWO here: with an official board the LED flickers during SWD and loads the line, so remove the LED or its series resistor, or use the clone.

## Repository

```
hardware/          KiCad project, fab outputs, BOM           CERN-OHL-P-2.0
docs/              pin mapping, assembly notes, renders      CC-BY-4.0
```

Firmware lives in the [main repository](https://github.com/ionos-sdr/ionos-sdr): `firmware-fg23/` for the radio SoC, `firmware-esp32/` for the companion.

## Credits, licensing, trademarks

Hardware under CERN-OHL-P-2.0, documentation under CC-BY-4.0. Not affiliated with IONOS SE or Silicon Laboratories; EFR32, Simplicity Studio and the WSTK radio board interface are Silicon Labs property, used here for interoperability only.

Designed by Zoltán Dóczi and Zoltán Papp at [Z2 Labs](https://www.z2labs.io/), Budapest. Design and manufacturing support by [Protowoerk](https://www.protowoerk.com).

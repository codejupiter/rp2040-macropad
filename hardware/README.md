# Hardware

This directory contains the editable KiCad 10 source for the 58 x 97 mm, two-layer macropad PCB.

## Files

- `MacroPad.kicad_pro` — KiCad project settings
- `MacroPad.kicad_sch` — electrical schematic
- `MacroPad.kicad_pcb` — routed PCB and board outline
- `BOM.csv` — machine-readable bill of materials
- `manufacturing/macropad_gerbers.zip` — manufacturer-ready fabrication archive
- `reports/` — saved electrical-rule and design-rule results

The local symbol and footprint tables use KiCad's `KICAD10_SYMBOL_DIR` and `KICAD10_FOOTPRINT_DIR` variables, so the project does not depend on a machine-specific application path.

## Electrical conventions

| Net | Pico pin | Function |
| --- | --- | --- |
| `ROW0` | GP0 / physical pin 1 | Driven low while scanning SW1 and SW2 |
| `ROW1` | GP1 / physical pin 2 | Driven low while scanning SW3 and SW4 |
| `COL0` | GP6 / physical pin 9 | Pulled-up input for SW1 and SW3 |
| `COL1` | GP7 / physical pin 10 | Pulled-up input for SW2 and SW4 |

Every switch connects from a column to a diode anode. Every diode cathode connects to its row. The cathode is the striped end of a physical 1N4148 and is marked `K` on the silkscreen.

## Fabrication defaults

- 58 x 97 mm finished size
- 2 layers
- 1.6 mm FR-4
- 1 oz copper
- Red solder mask
- White silkscreen

Inspect the Gerber archive with the board house viewer before checkout. The ZIP intentionally contains only fabrication files; editable source remains here in the repository.

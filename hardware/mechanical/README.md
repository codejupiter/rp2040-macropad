# Mechanical enclosure, plate, and exploded assembly

This directory contains the repo-native mechanical layer for the 2×2 macropad. The generator reads `hardware/MacroPad.kicad_pcb` directly instead of maintaining a second set of PCB coordinates. If the board outline, mounting holes, Pico footprint, or switch positions move, regeneration either follows the new values or stops when the expected 2×2 design invariants no longer hold.

![Exploded macropad assembly](../../docs/images/macropad-exploded-assembly.gif)

## Generated mechanical files

| Part | Size | Purpose |
| --- | --- | --- |
| `bottom_enclosure` | 64 × 103 × 12.6 mm | Printable tray, 3 mm walls, 2.4 mm floor, and four PCB-aligned M2 posts |
| `switch_plate` | 64 × 103 × 1.5 mm | Four 14 mm MX openings, Pico access opening, and four M2 holes |
| `pcb_from_kicad` | 58 × 97 × 1.6 mm | Visualization body generated from Edge.Cuts with every drilled footprint pad removed |
| `mx_switch_proxy` | 15.6 × 15.6 mm body | Assembly envelope for each committed 1u MX footprint |
| `keycap_proxy` | 18 × 18 mm | Assembly envelope for each 1u keycap listed in the BOM |
| `diode_proxy` | 7.62 mm lead pitch | DO-35 assembly envelope |
| `pico_proxy` | 21 × 53.5 mm envelope | Pico board, headers, processor, and USB connector visualization |

Printable meshes are in [`stl/`](stl/), while editable manufacturing exchange files are in [`step/`](step/). The component proxies communicate clearance and assembly order; they are not replacements for component-manufacturer production models.

## Source-of-truth mapping

The generator derives these values from the KiCad file:

- 58 × 97 mm `Edge.Cuts` rectangle;
- all plated and non-plated drill positions;
- H1–H4 M2 mounting centers;
- the true MX switch centers, including the KiCad footprint-origin offset;
- 19.05 mm horizontal and vertical switch pitch;
- D1–D4 center positions; and
- the A1 Raspberry Pi Pico pad envelope.

The case margin, wall/floor thicknesses, 14 mm MX plate opening, 5 mm PCB-to-plate clearance, and print tolerances are mechanical design parameters declared near the top of `generate_assembly.py`.

## Regenerate everything

Python 3.11 or 3.12 is recommended for CadQuery/OpenCascade compatibility. The animation also requires `ffmpeg` on `PATH`.

```bash
python3.12 -m venv .venv-mechanical
source .venv-mechanical/bin/activate
python -m pip install -r hardware/mechanical/requirements.txt
python hardware/mechanical/generate_assembly.py
```

Use `--skip-animation` to regenerate CAD and the static exploded PNG without encoding GIF/MP4 media.

Every exported STL is reloaded and checked for watertight geometry and consistent triangle winding. The enclosure and plate must each remain a single connected printable body.

## Printing baseline

- Material: PETG, ABS/ASA, or reinforced nylon
- Layer height: 0.20 mm
- Perimeters: 4
- Top/bottom layers: 5
- Infill: 25–30% gyroid
- Enclosure orientation: floor on the build plate
- Plate orientation: either broad face on the build plate
- Dimensional compensation: print a small 14 mm switch-fit coupon first

The M2 holes are modeled at 2.2 mm. Depending on printer calibration, clear them with a 2.2 mm drill by hand rather than forcing screws through undersized plastic.

## Important design decisions

The four switches are 1u MX footprints. They do **not** use keyboard stabilizers; stabilizers are normally required for wider keys such as 2u and above. Adding them to this design would introduce incorrect holes and misleading assembly instructions.

The Pico access opening deliberately remains open because the committed PCB places its USB connector inside the board perimeter. This provides top access to the USB connector instead of inventing an unsupported side-entry cable path.

This is a first printable revision derived from the PCB, not a substitute for a physical fit test. Verify the actual switch clip geometry, Pico header height, USB plug clearance, screw length, and printer shrinkage before ordering multiple sets.

# Assembly and bring-up

## What you need

- One Raspberry Pi Pico (RP2040)
- Four MX-compatible switches and four keycaps
- Four 1N4148 through-hole diodes
- Two 1x20 male headers, plus sockets if you want a removable Pico
- Soldering iron, solder, flush cutters, and a multimeter
- A data-capable Micro-USB cable

## Assembly order

1. **Inspect the bare PCB.** Check for damaged plating, scratches across traces, or debris in the Pico and switch holes.
2. **Install D1–D4.** Bend each lead to 7.62 mm pitch. Match the diode's painted stripe to the PCB pad marked `K`; the stripe faces the associated row net.
3. **Solder the diodes.** Tack one lead, confirm the body is flat and polarity is correct, then solder the second lead and trim both.
4. **Install the Pico headers.** Use sockets on the macropad PCB if you want the Pico removable. Keep both rows square and parallel.
5. **Orient the Pico.** The Pico USB connector faces the bottom board edge near the `A1` marking. Confirm orientation before soldering.
6. **Install SW1–SW4.** Seat every switch flat against the board before soldering both electrical pins.
7. **Add optional mounting hardware.** The four corner holes accept M2 hardware.

## Checks before power

With the board disconnected:

- Confirm there is no short between 3V3 and GND.
- Confirm no adjacent Pico header pads are bridged.
- Check each diode in diode-test mode; it should conduct in only one direction.
- Verify all four diode stripes align with the `K` silkscreen marks.
- Press each switch and check continuity through its switch/diode path.

## First flash

Build the firmware from the repository root, then run:

```bash
./flash_macropad.sh
```

If needed, hold **BOOTSEL** while connecting the Pico. After the script reports success, the board should enumerate as `RP2040 2x2 Macropad`.

Open a text editor and test SW1 through SW4. The default keymap produces `A`, `B`, `C`, and `D`. Also test simultaneous presses to confirm the matrix and diodes are working correctly.

## Troubleshooting

- **No USB device:** try a known data cable, inspect the Pico's USB connector, and re-enter BOOTSEL.
- **One dead key:** inspect that switch and its diode joints, then verify diode polarity.
- **A row or column is dead:** inspect the relevant Pico header pin and continuity to GP0, GP1, GP6, or GP7.
- **Keys are swapped:** confirm the installed firmware uses the pin map and keymap in `main.cpp`.
- **A key repeats or chatters:** reflow its joints, test the switch, or increase `kDebounceMs`.

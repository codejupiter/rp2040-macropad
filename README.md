# RP2040 Custom 2x2 USB Mechanical Macropad

![RP2040](https://img.shields.io/badge/MCU-RP2040-C51A4A?style=flat-square)
![C++17](https://img.shields.io/badge/firmware-C%2B%2B17-00599C?style=flat-square&logo=cplusplus)
![TinyUSB](https://img.shields.io/badge/USB-TinyUSB_HID-6F42C1?style=flat-square)
![KiCad](https://img.shields.io/badge/PCB-KiCad_10-314CB0?style=flat-square&logo=kicad)
![PCB](https://img.shields.io/badge/board-58_x_97_mm-E31B23?style=flat-square)

A compact, purpose-built USB mechanical macropad based on the Raspberry Pi Pico and RP2040. The project combines a diode-isolated 2x2 mechanical switch matrix, a custom two-layer KiCad PCB, and native USB HID keyboard firmware written with the official Raspberry Pi Pico C/C++ SDK and TinyUSB.

The finished macropad enumerates as a standard keyboard. It requires no desktop application, background service, or custom host driver.

## Overview

| Area | Specification |
| --- | --- |
| Microcontroller | Raspberry Pi Pico with RP2040 |
| Input layout | 2x2 mechanical switch matrix |
| Switch isolation | One 1N4148 diode per switch for anti-ghosting |
| USB interface | TinyUSB HID boot keyboard |
| Firmware | C++17 with the official Pico SDK |
| PCB | 58 x 97 mm, two copper layers, red solder mask |
| Design tools | KiCad |
| Host requirements | None beyond standard USB HID support |

### Highlights

- Four independently mapped mechanical keys
- Diode-isolated matrix for reliable multi-key input
- Debounced matrix scanning with rows driven low only while sampled
- Standard USB HID keyboard reports with no custom driver
- Pico unique-ID-based USB serial number
- Remote-wakeup support when permitted by the host
- Project-local TinyUSB configuration propagated through CMake
- USB stdio disabled to avoid collisions with the custom TinyUSB device stack
- Automated flashing through `picotool` or the Pico's mounted BOOTSEL volume
- KiCad schematic, routed PCB, and manufacturer-ready Gerber/drill outputs

## Hardware Architecture

The keyboard matrix uses two row nets and two column nets. Each column is read as an input with an internal pull-up. During scanning, the firmware drives one row low at a time and samples both columns; inactive rows return to a high-impedance state.

Each switch is wired in series with a 1N4148 diode. The diode's **anode faces the switch** and its **cathode (striped end) faces the row net**. This direction allows a pulled-up column to discharge through a pressed switch into the selected low row while preventing reverse-current paths through neighboring switches.

```text
                    COL0                    COL1
                      |                       |
                 +----+----+             +----+----+
                 |   SW1   |             |   SW2   |
                 +----+----+             +----+----+
                      |                       |
                    |>| D1                  |>| D2
                      |                       |
                      +--------- ROW0 --------+

                 +----+----+             +----+----+
                 |   SW3   |             |   SW4   |
                 +----+----+             +----+----+
                      |                       |
                    |>| D3                  |>| D4
                      |                       |
                      +--------- ROW1 --------+
```

> **Diode orientation:** the bar in the diode symbol represents the cathode and corresponds to the painted stripe on a physical 1N4148.

## Bill of Materials

| Qty. | Reference | Component | Notes |
| ---: | --- | --- | --- |
| 1 | A1 | Raspberry Pi Pico | RP2040 module; Pico or pin-compatible original-form-factor board |
| 4 | SW1-SW4 | MX-compatible mechanical switch | PCB-mount or plate-mount, depending on enclosure design |
| 4 | D1-D4 | 1N4148 small-signal diode | DO-35 through-hole package |
| 4 | K1-K4 | MX-compatible keycap | Any preferred profile and legend |
| 2 | J1-J2 | 1x20, 2.54 mm headers | Use sockets for a removable Pico |
| 1 | PCB | Custom two-layer PCB | 58 x 97 mm, 1.6 mm FR-4 recommended, red solder mask |
| 4 | H1-H4 | M2 hardware | Optional screws and standoffs for a case or baseplate |
| 1 | — | USB cable | Match the connector fitted to the selected Pico revision |

## KiCad Schematic and PCB Design

The KiCad design contains the complete switch matrix, four isolation diodes, the Raspberry Pi Pico module footprint, a closed `Edge.Cuts` outline, front and back copper routing, and four M2 mounting holes.

Key manufacturing characteristics:

- **Board size:** 58 x 97 mm
- **Layer count:** 2
- **Copper routing:** front and back
- **Solder mask:** red
- **Switch spacing:** standard 19.05 mm keyboard pitch
- **Mounting:** four M2 non-plated holes
- **Validation:** zero unrouted connections, shorts, or copper-clearance errors

The fabrication package should include:

- Front and back copper
- Front and back solder mask
- Front and back silkscreen
- `Edge.Cuts`
- Plated through-hole drill file
- Non-plated through-hole drill file

Always inspect the Gerbers in an independent viewer before ordering. Confirm the board dimensions, drill separation, switch orientation, Pico USB access, and diode polarity against the assembled hardware.

## Firmware

The firmware is intentionally small and direct:

- `main.cpp` implements matrix scanning, debouncing, USB descriptors, keyboard reports, and remote wakeup.
- `tusb_config.h` configures the RP2040's native USB controller as a full-speed TinyUSB device with one HID interface.
- `CMakeLists.txt` propagates the custom TinyUSB configuration to the SDK build and disables Pico USB/UART stdio.
- `flash_macropad.sh` watches for a connected Pico and flashes the generated UF2 automatically.

The default keymap sends `A`, `B`, `C`, and `D`:

```cpp
constexpr uint8_t kKeymap[2][2] = {
    {HID_KEY_A, HID_KEY_B},
    {HID_KEY_C, HID_KEY_D},
};
```

Edit `kKeymap` in `main.cpp` to assign media controls, modifiers, navigation keys, shortcuts, or application-specific commands supported by the HID report descriptor.

> The example USB VID/PID values are intended for development. Obtain an appropriate VID/PID allocation before distributing a commercial product.

## Firmware Build Instructions

### Prerequisites

- CMake 3.13 or newer
- A C/C++ build tool supported by CMake, such as Ninja or Make
- Arm GNU Toolchain for `arm-none-eabi`
- The official [Raspberry Pi Pico C/C++ SDK](https://github.com/raspberrypi/pico-sdk), including its submodules

Point `PICO_SDK_PATH` to the SDK installation or place `pico_sdk_import.cmake` beside this project's `CMakeLists.txt`.

### Configure and build

```bash
export PICO_SDK_PATH=/absolute/path/to/pico-sdk

cmake -S . -B build-full \
  -DCMAKE_BUILD_TYPE=Release \
  -DPICO_SDK_PATH="$PICO_SDK_PATH"

cmake --build build-full --parallel
```

The primary flash image is generated at:

```text
build-full/pico_macropad.uf2
```

The build also emits ELF, BIN, HEX, disassembly, and linker-map artifacts for debugging and inspection.

## Flashing and Usage

### Automated flashing

Make the watcher executable once, then launch it with the UF2 path:

```bash
chmod +x ./flash_macropad.sh
./flash_macropad.sh ./build-full/pico_macropad.uf2
```

The script uses the first available method:

1. A USB-capable `picotool` installation, using verified load and reboot options.
2. The operating system's mounted `RPI-RP2` or `RP2350` BOOTSEL volume.

Leave the watcher running, hold **BOOTSEL** while connecting the Pico if required, and release it once the drive appears. The script flashes the UF2, flushes filesystem buffers, and exits after the Pico reboots.

To change the polling interval:

```bash
PICO_FLASH_POLL_SECONDS=0.25 ./flash_macropad.sh ./build-full/pico_macropad.uf2
```

### Manual flashing

1. Disconnect the Pico.
2. Hold the **BOOTSEL** button.
3. Connect USB while continuing to hold BOOTSEL.
4. Release the button when the `RPI-RP2` volume appears.
5. Copy `pico_macropad.uf2` onto the mounted volume.

The drive disconnects automatically when flashing completes.

### Using the macropad

After reboot, the board appears as a standard USB keyboard. No host-side installation is required on macOS, Windows, Linux, or other systems with USB HID keyboard support. Pressing a switch sends the corresponding key from `kKeymap`; releasing it sends an updated keyboard report.

## Troubleshooting

### TinyUSB reports that `CFG_TUD_RHPORT0_MODE` or `CFG_TUD_RHPORT1_MODE` is undefined

Confirm that:

- `tusb_config.h` defines `CFG_TUSB_RHPORT0_MODE` and its compatibility alias.
- `CFG_TUSB_CONFIG_FILE=\"tusb_config.h\"` is exported by the interface target in `CMakeLists.txt`.
- The project directory is included in TinyUSB's compile-time include path.
- `pico_enable_stdio_usb(... 0)` remains disabled for this custom device configuration.
- The build directory is deleted or reconfigured after changing TinyUSB settings.

### The Pico is not detected by the flashing script

- Use a data-capable USB cable.
- Enter BOOTSEL mode before connecting the cable.
- Check that `RPI-RP2` appears in Finder, Explorer, or your Linux mount directory.
- Pass the UF2 path explicitly if using a non-default build directory.
- If using `picotool`, confirm that it was built with USB/libusb support and exposes the `load` command.

### Keys are missing, swapped, or remain pressed

- Verify that firmware row/column constants match the PCB nets.
- Check diode polarity; each cathode stripe must face its row net.
- Inspect switch and header solder joints.
- Confirm that the correct Pico pins are seated in the PCB headers.
- Increase the debounce interval if a particular switch is unusually noisy.

## Contributing

Issues and pull requests are welcome. When proposing hardware changes, include updated KiCad source files and regenerated manufacturing outputs. Firmware changes should build cleanly with the official Pico SDK and preserve standard USB HID behavior.

Before submitting a change:

1. Build the firmware from a clean build directory.
2. Test every switch individually and in multi-key combinations.
3. Run KiCad ERC and DRC.
4. Inspect regenerated Gerber and drill outputs.
5. Document any pin-map, footprint, USB descriptor, or BOM changes.

---

Built for experimentation, repeatable hardware iteration, and a satisfyingly small number of very clicky buttons.

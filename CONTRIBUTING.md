# Contributing

Thank you for helping improve the macropad. Small, focused pull requests are easiest to review.

## Firmware changes

1. Create a branch from `main`.
2. Configure and build from a clean directory.
3. Flash real hardware and test every key alone and in multi-key combinations.
4. Describe any USB descriptor, pin-map, or behavior change in the pull request.

```bash
export PICO_SDK_PATH=/absolute/path/to/pico-sdk
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

## Hardware changes

Use KiCad 10 or a compatible newer version. A hardware pull request should include:

- updated `.kicad_sch`, `.kicad_pcb`, and project files;
- ERC and DRC results with no new electrical or manufacturing errors;
- regenerated schematic, PCB, and 3D-render images;
- regenerated and independently inspected Gerber/drill outputs;
- an updated BOM and assembly guide when parts or footprints change.

Do not commit KiCad lock files, personal UI state, autosaves, or build directories.

## Commit and pull-request style

Use an imperative subject such as `firmware: add media-key report` or `hardware: widen mounting-hole clearance`. Explain the motivation, how the change was verified, and attach useful photos or viewer screenshots for physical changes.

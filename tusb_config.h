#ifndef MACROPAD_TUSB_CONFIG_H
#define MACROPAD_TUSB_CONFIG_H

// The Pico SDK supplies CFG_TUSB_MCU=OPT_MCU_RP2040 and
// CFG_TUSB_OS=OPT_OS_PICO through its TinyUSB CMake targets.

// RP2040 has one native USB controller: root-hub port 0, device mode,
// full-speed. Defining this explicitly also makes zero-argument tusb_init()
// valid with current TinyUSB releases.
#define CFG_TUSB_RHPORT0_MODE (OPT_MODE_DEVICE | OPT_MODE_FULL_SPEED)

// TinyUSB versions bundled with older Pico SDK releases used the CFG_TUD_*
// spelling for the same setting. Keeping the alias makes this config portable
// across both APIs.
#define CFG_TUD_RHPORT0_MODE CFG_TUSB_RHPORT0_MODE

#define CFG_TUD_ENABLED 1
#define CFG_TUD_MAX_SPEED OPT_MODE_FULL_SPEED

#ifndef CFG_TUSB_DEBUG
#define CFG_TUSB_DEBUG 0
#endif

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE 64
#endif

#ifndef CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_SECTION
#endif

#ifndef CFG_TUSB_MEM_ALIGN
#define CFG_TUSB_MEM_ALIGN __attribute__((aligned(4)))
#endif

// This device exposes one HID keyboard and no other USB classes.
#define CFG_TUD_HID 1
#define CFG_TUD_CDC 0
#define CFG_TUD_MSC 0
#define CFG_TUD_MIDI 0
#define CFG_TUD_VENDOR 0

// A boot-keyboard input report is 8 bytes; 16 leaves comfortable headroom.
#define CFG_TUD_HID_EP_BUFSIZE 16

#endif  // MACROPAD_TUSB_CONFIG_H

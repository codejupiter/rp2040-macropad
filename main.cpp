#include <cstddef>
#include <cstdint>
#include <cstring>

#include "bsp/board_api.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include "tusb.h"

namespace {

constexpr std::size_t kRowCount = 2;
constexpr std::size_t kColumnCount = 2;

// Keep this pin map synchronized with hardware/MacroPad.kicad_sch.
constexpr uint kRowPins[kRowCount] = {0, 1};
constexpr uint kColumnPins[kColumnCount] = {6, 7};

// Change these four usages to whatever shortcuts the macropad should send.
constexpr uint8_t kKeymap[kRowCount][kColumnCount] = {
    {HID_KEY_A, HID_KEY_B},
    {HID_KEY_C, HID_KEY_D},
};

constexpr uint32_t kDebounceMs = 5;

enum : uint8_t {
    kInterfaceHid = 0,
    kInterfaceCount,
};

constexpr uint8_t kHidEndpoint = 0x81;
constexpr uint16_t kUsbVid = 0xCAFE;  // TinyUSB example VID; replace for a product.
constexpr uint16_t kUsbPid = 0x4004;
constexpr uint16_t kUsbBcd = 0x0200;
constexpr uint16_t kConfigurationLength =
    TUD_CONFIG_DESC_LEN + TUD_HID_DESC_LEN;

const tusb_desc_device_t kDeviceDescriptor = {
    sizeof(tusb_desc_device_t),  // bLength
    TUSB_DESC_DEVICE,            // bDescriptorType
    kUsbBcd,                     // bcdUSB
    0x00,                        // bDeviceClass (specified per interface)
    0x00,                        // bDeviceSubClass
    0x00,                        // bDeviceProtocol
    CFG_TUD_ENDPOINT0_SIZE,      // bMaxPacketSize0
    kUsbVid,                     // idVendor
    kUsbPid,                     // idProduct
    0x0100,                      // bcdDevice
    0x01,                        // iManufacturer
    0x02,                        // iProduct
    0x03,                        // iSerialNumber
    0x01,                        // bNumConfigurations
};

const uint8_t kHidReportDescriptor[] = {
    TUD_HID_REPORT_DESC_KEYBOARD()
};

const uint8_t kConfigurationDescriptor[] = {
    // Configuration number, interface count, string index, total length,
    // attributes, and maximum current in mA.
    TUD_CONFIG_DESCRIPTOR(
        1,
        kInterfaceCount,
        0,
        kConfigurationLength,
        TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP,
        100),

    // Interface number, string index, boot protocol, report descriptor length,
    // endpoint address, endpoint size, and polling interval in milliseconds.
    TUD_HID_DESCRIPTOR(
        kInterfaceHid,
        0,
        HID_ITF_PROTOCOL_KEYBOARD,
        sizeof(kHidReportDescriptor),
        kHidEndpoint,
        CFG_TUD_HID_EP_BUFSIZE,
        5),
};

const char* const kStringDescriptors[] = {
    nullptr,              // 0: handled separately as language ID
    "Macro Lab",          // 1: manufacturer
    "RP2040 2x2 Macropad",// 2: product
    nullptr,              // 3: generated from the Pico unique ID
};

uint16_t gStringDescriptor[33];
bool gRemoteWakeupEnabled = false;
bool gRemoteWakeupSent = false;

void initialize_matrix() {
    // Rows are normally high impedance. During a scan, one row at a time is
    // driven low, which keeps inactive rows electrically out of the matrix.
    for (uint pin : kRowPins) {
        gpio_init(pin);
        gpio_put(pin, false);
        gpio_set_dir(pin, GPIO_IN);
        gpio_disable_pulls(pin);
    }

    for (uint pin : kColumnPins) {
        gpio_init(pin);
        gpio_set_dir(pin, GPIO_IN);
        gpio_pull_up(pin);
    }
}

uint8_t scan_matrix() {
    uint8_t pressed = 0;

    for (std::size_t row = 0; row < kRowCount; ++row) {
        const uint row_pin = kRowPins[row];
        gpio_put(row_pin, false);
        gpio_set_dir(row_pin, GPIO_OUT);
        sleep_us(3);

        for (std::size_t column = 0; column < kColumnCount; ++column) {
            if (!gpio_get(kColumnPins[column])) {
                const std::size_t bit = row * kColumnCount + column;
                pressed |= static_cast<uint8_t>(1u << bit);
            }
        }

        gpio_set_dir(row_pin, GPIO_IN);
    }

    return pressed;
}

void send_keyboard_state(uint8_t matrix_state) {
    uint8_t keycodes[6] = {};
    std::size_t key_count = 0;

    for (std::size_t row = 0; row < kRowCount; ++row) {
        for (std::size_t column = 0; column < kColumnCount; ++column) {
            const std::size_t bit = row * kColumnCount + column;
            if ((matrix_state & (1u << bit)) != 0 &&
                key_count < sizeof(keycodes)) {
                keycodes[key_count++] = kKeymap[row][column];
            }
        }
    }

    tud_hid_keyboard_report(0, 0, keycodes);
}

void matrix_task() {
    static uint8_t candidate_state = 0;
    static uint8_t stable_state = 0;
    static uint8_t reported_state = 0xFF;
    static uint32_t candidate_since_ms = 0;

    const uint8_t raw_state = scan_matrix();
    const uint32_t now_ms = to_ms_since_boot(get_absolute_time());

    if (raw_state != candidate_state) {
        candidate_state = raw_state;
        candidate_since_ms = now_ms;
    } else if (stable_state != candidate_state &&
               static_cast<uint32_t>(now_ms - candidate_since_ms) >=
                   kDebounceMs) {
        stable_state = candidate_state;
        gRemoteWakeupSent = false;
    }

    if (stable_state != 0 && tud_suspended() && gRemoteWakeupEnabled &&
        !gRemoteWakeupSent) {
        tud_remote_wakeup();
        gRemoteWakeupSent = true;
    }

    if (stable_state != reported_state && tud_hid_ready()) {
        send_keyboard_state(stable_state);
        reported_state = stable_state;
    }
}

}  // namespace

extern "C" uint8_t const* tud_descriptor_device_cb() {
    return reinterpret_cast<uint8_t const*>(&kDeviceDescriptor);
}

extern "C" uint8_t const* tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return kHidReportDescriptor;
}

extern "C" uint8_t const* tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return kConfigurationDescriptor;
}

extern "C" uint16_t const* tud_descriptor_string_cb(uint8_t index,
                                                     uint16_t language_id) {
    (void)language_id;
    std::size_t character_count = 0;

    if (index == 0) {
        gStringDescriptor[1] = 0x0409;  // English (United States)
        character_count = 1;
    } else if (index == 3) {
        character_count = board_usb_get_serial(gStringDescriptor + 1, 32);
    } else {
        constexpr std::size_t kStringCount =
            sizeof(kStringDescriptors) / sizeof(kStringDescriptors[0]);
        if (index >= kStringCount || kStringDescriptors[index] == nullptr) {
            return nullptr;
        }

        const char* string = kStringDescriptors[index];
        character_count = std::strlen(string);
        if (character_count > 32) {
            character_count = 32;
        }

        for (std::size_t i = 0; i < character_count; ++i) {
            gStringDescriptor[1 + i] = static_cast<uint8_t>(string[i]);
        }
    }

    gStringDescriptor[0] = static_cast<uint16_t>(
        (TUSB_DESC_STRING << 8) | (2 * character_count + 2));
    return gStringDescriptor;
}

extern "C" uint16_t tud_hid_get_report_cb(uint8_t instance,
                                            uint8_t report_id,
                                            hid_report_type_t report_type,
                                            uint8_t* buffer,
                                            uint16_t requested_length) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)requested_length;
    return 0;
}

extern "C" void tud_hid_set_report_cb(uint8_t instance,
                                       uint8_t report_id,
                                       hid_report_type_t report_type,
                                       uint8_t const* buffer,
                                       uint16_t buffer_size) {
    // Hosts use an OUTPUT report for Caps Lock/Num Lock LEDs. This macropad has
    // no lock LEDs, so acknowledging and ignoring the report is intentional.
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)buffer_size;
}

extern "C" void tud_mount_cb() {
    gRemoteWakeupSent = false;
}

extern "C" void tud_suspend_cb(bool remote_wakeup_enabled) {
    gRemoteWakeupEnabled = remote_wakeup_enabled;
    gRemoteWakeupSent = false;
}

extern "C" void tud_resume_cb() {
    gRemoteWakeupEnabled = false;
    gRemoteWakeupSent = false;
}

int main() {
    board_init();
    initialize_matrix();

    // CFG_TUSB_RHPORT0_MODE in tusb_config.h makes this unambiguously initialize
    // the RP2040's native USB controller as a full-speed device.
    tusb_init();

    while (true) {
        tud_task();
        matrix_task();
        tight_loop_contents();
    }
}

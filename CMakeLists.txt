cmake_minimum_required(VERSION 3.13)

# The carrier PCB and pin map target the original Raspberry Pi Pico.
set(PICO_BOARD pico CACHE STRING "Pico SDK board target")

# Prefer a project-local copy of pico_sdk_import.cmake when one is present.
# Otherwise use the SDK selected by -DPICO_SDK_PATH=... or PICO_SDK_PATH.
if (EXISTS "${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake")
elseif (DEFINED PICO_SDK_PATH)
    include("${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
elseif (DEFINED ENV{PICO_SDK_PATH})
    include("$ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake")
else()
    message(FATAL_ERROR
        "Pico SDK not found. Set PICO_SDK_PATH or copy "
        "pico_sdk_import.cmake into this directory.")
endif()

project(rp2040_macropad C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

pico_sdk_init()

# Carry tusb_config.h as a usage requirement. TinyUSB is supplied by the Pico
# SDK as interface sources, so these settings are also present while those
# sources are compiled as part of macropad.
add_library(macropad_tusb_config INTERFACE)
target_include_directories(macropad_tusb_config INTERFACE
    "${CMAKE_CURRENT_LIST_DIR}"
)
target_compile_definitions(macropad_tusb_config INTERFACE
    CFG_TUSB_CONFIG_FILE=\"tusb_config.h\"
)

add_executable(macropad
    main.cpp
)

target_link_libraries(macropad PRIVATE
    pico_stdlib
    macropad_tusb_config
    tinyusb_device
    tinyusb_board
)

# This firmware owns the USB controller through TinyUSB. Enabling Pico USB
# stdio here would create a second device-stack configuration and collide with
# the custom HID descriptors. UART stdio is also disabled because it is unused.
pico_enable_stdio_usb(macropad 0)
pico_enable_stdio_uart(macropad 0)

pico_add_extra_outputs(macropad)

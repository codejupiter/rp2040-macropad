#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_UF2="${SCRIPT_DIR}/build/macropad.uf2"
UF2_PATH="${1:-${DEFAULT_UF2}}"
POLL_SECONDS="${PICO_FLASH_POLL_SECONDS:-0.5}"

if [[ ! -f "${UF2_PATH}" ]]; then
    printf 'Firmware not found: %s\n' "${UF2_PATH}" >&2
    printf 'Usage: %s [path/to/macropad.uf2]\n' "$0" >&2
    exit 1
fi

UF2_PATH="$(CDPATH= cd -- "$(dirname -- "${UF2_PATH}")" && pwd)/$(basename -- "${UF2_PATH}")"

PICOTOOL_BIN=""
if [[ -n "${PICOTOOL:-}" && -x "${PICOTOOL}" ]]; then
    PICOTOOL_BIN="${PICOTOOL}"
elif command -v picotool >/dev/null 2>&1; then
    PICOTOOL_BIN="$(command -v picotool)"
fi

# Builds made with PICOTOOL_NO_LIBUSB can inspect files but cannot flash USB
# devices. Such a binary does not expose the load command, so ignore it.
if [[ -n "${PICOTOOL_BIN}" ]] &&
   ! "${PICOTOOL_BIN}" help 2>&1 | grep -Eq '^[[:space:]]+load[[:space:]]'; then
    PICOTOOL_BIN=""
fi

find_bootsel_volume() {
    local volume
    local -a candidates=(
        "/Volumes/RPI-RP2"
        "/Volumes/RP2350"
        "/media/${USER:-user}/RPI-RP2"
        "/media/${USER:-user}/RP2350"
        "/run/media/${USER:-user}/RPI-RP2"
        "/run/media/${USER:-user}/RP2350"
    )

    for volume in "${candidates[@]}"; do
        if [[ -d "${volume}" ]] &&
           { [[ -f "${volume}/INFO_UF2.TXT" ]] ||
             [[ -f "${volume}/INDEX.HTM" ]]; }; then
            printf '%s\n' "${volume}"
            return 0
        fi
    done

    return 1
}

flash_mounted_volume() {
    local volume="$1"
    local destination="${volume}/$(basename -- "${UF2_PATH}")"

    printf '\nPico BOOTSEL drive detected at %s\n' "${volume}"
    printf 'Copying %s...\n' "$(basename -- "${UF2_PATH}")"

    /bin/cp "${UF2_PATH}" "${destination}"

    # The BOOTSEL drive normally disappears immediately after accepting the
    # UF2. Flush any remaining host-side filesystem buffers when possible.
    sync || true

    printf 'Flash complete. The Pico is rebooting into the macropad firmware.\n'
}

printf 'Firmware: %s\n' "${UF2_PATH}"

if [[ -n "${PICOTOOL_BIN}" ]]; then
    printf 'Flasher:  %s (USB-capable)\n' "${PICOTOOL_BIN}"
else
    printf 'Flasher:  RPI-RP2 auto-mount fallback\n'
fi

printf 'Waiting for the Pico'
if [[ -z "${PICOTOOL_BIN}" ]]; then
    printf ' in BOOTSEL mode'
fi
printf '. Press Ctrl-C to cancel.\n'

trap 'printf "\nCancelled.\n"; exit 130' INT TERM

while true; do
    if [[ -n "${PICOTOOL_BIN}" ]]; then
        PICOTOOL_LOG="$(mktemp -t macropad-picotool.XXXXXX)"

        # -f also handles compatible firmware that exposes the Pico SDK USB
        # reset interface. Custom HID-only firmware still needs BOOTSEL once.
        if "${PICOTOOL_BIN}" load -f -u -v -x "${UF2_PATH}" \
            >"${PICOTOOL_LOG}" 2>&1; then
            printf '\n'
            cat "${PICOTOOL_LOG}"
            rm -f "${PICOTOOL_LOG}"
            printf 'Flash complete.\n'
            exit 0
        fi

        rm -f "${PICOTOOL_LOG}"
    fi

    if BOOTSEL_VOLUME="$(find_bootsel_volume)"; then
        flash_mounted_volume "${BOOTSEL_VOLUME}"
        exit 0
    fi

    sleep "${POLL_SECONDS}"
done

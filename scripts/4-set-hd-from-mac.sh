#!/bin/bash
# Enable HD/Remastered (paid content) from this Mac's own Battle.net login, no Windows PC needed.
# Mac Battle.net keeps its offline cookie in ~/Library/Application Support/Blizzard Entertainment/
# ClientSdk/cookie.bin, keyed with this Mac's IOPlatformUUID and Wi-Fi MAC address. This copies it
# into the prefix unchanged and sets MachineGuid and the C: volume serial so the Windows game
# derives the same key (see tools/mac_cookie_identity.py). This quits ShieldBattery if it's running.
#
# Usage: 4-set-hd-from-mac.sh
#   Log in to Battle.net on this Mac and start StarCraft: Remastered from it once first.
#   Run it again when HD stops working (new cookie, or macOS rotated the private Wi-Fi address).
set -euo pipefail
. "$(dirname "$0")/common.sh"

cookie="$HOME/Library/Application Support/Blizzard Entertainment/ClientSdk/cookie.bin"
[ -f "$cookie" ] || { echo "missing $cookie: start StarCraft: Remastered from Battle.net once"; exit 1; }
uuid=$(ioreg -rd1 -c IOPlatformExpertDevice | sed -n 's/.*"IOPlatformUUID" = "\(.*\)"/\1/p')
# Read MACs here: macOS shows some processes (Homebrew Python, for one) 02:00:00:00:00:00 instead.
macs=$(ifconfig | awk '/ether/ {print $2}' | sort -u)

mkdir -p "$DRIVE_C/sbtools"
serial=$(python3 -I "$(dirname "$0")/../tools/mac_cookie_identity.py" "$cookie" "$DRIVE_C/sbtools/machine-guid.reg" "$uuid" $macs)

wkill
ck="$DRIVE_C/users/Sikarugir/AppData/Local/Blizzard Entertainment/ClientSdk"
mkdir -p "$ck"
cp "$cookie" "$ck/cookie.bin"
# Wine's mount manager reads the drive serial from this file when Wine starts.
printf '%s\n' "$serial" > "$DRIVE_C/.windows-serial"
# MachineGuid holds non-ASCII and control characters, which reg.exe in a .bat can't pass; regedit
# imports them exactly from a hex(1) value.
printf 'regedit /s C:\\sbtools\\machine-guid.reg\r\n' > "$DRIVE_C/sbtools/set-guid.bat"
wrun "$DRIVE_C/sbtools/set-guid.bat" >/dev/null 2>&1
wkill
echo "Set: cookie copied, C: volume serial $serial, MachineGuid from this Mac. Open ShieldBattery."

#!/bin/bash
# Sharp ShieldBattery client on a Retina screen. Without this Wine reports the screen in points
# (1440x900 on a 13" MacBook Air) and macOS scales the window up, so text is blurry. This turns on
# Wine's Retina mode and sets Windows scaling to 200% (192 DPI), so the client keeps its size but
# draws at full pixel density. Wine applies Retina mode to the whole prefix (a per-app RetinaMode
# key under AppDefaults is ignored), so the game also renders at full resolution (2880x1800 there).
# This quits ShieldBattery if it's running.
#
# Usage: 5-retina.sh [on|off]   (default on; off restores Wine's defaults)
set -euo pipefail
. "$(dirname "$0")/common.sh"

mode="${1:-on}"
case "$mode" in
    on) retina=y dpi=192 ;;
    off) retina=n dpi=96 ;;
    *) echo "usage: $0 [on|off]"; exit 1 ;;
esac

wkill
mkdir -p "$DRIVE_C/sbtools"
printf '%s\r\n' \
    "reg add \"HKCU\\Software\\Wine\\Mac Driver\" /v RetinaMode /t REG_SZ /d $retina /f" \
    "reg add \"HKCU\\Control Panel\\Desktop\" /v LogPixels /t REG_DWORD /d $dpi /f" \
    > "$DRIVE_C/sbtools/set-retina.bat"
wrun_bat "$DRIVE_C/sbtools/set-retina.bat"
wkill
grep -q "\"RetinaMode\"=\"$retina\"" "$PREFIX/user.reg" || { echo "the setting didn't save, run this again"; exit 1; }
echo "Set: Retina mode $mode, $dpi DPI. Open ShieldBattery."

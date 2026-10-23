#!/bin/bash
# Put StarCraft: Remastered at C:\Program Files (x86)\StarCraft, ShieldBattery's default path.
# The source is either a Windows install folder (must contain x86/, x86_64/ and Data/), which
# is moved, or a macOS install (e.g. /Applications/StarCraft), which is copied and given the
# Windows executables for the same build from Blizzard's CDN. The Mac game keeps working.
# Usage: 2-install-game.sh /path/to/StarCraft
set -euo pipefail
. "$(dirname "$0")/common.sh"

src="${1:?usage: $0 /path/to/StarCraft}"
dst="$DRIVE_C/Program Files (x86)/StarCraft"
[ -e "$dst" ] && { echo "$dst already exists"; exit 1; }

if [ -d "$src/x86_64/StarCraft.app" ] && [ ! -e "$src/x86/StarCraft.exe" ]; then
    for f in .build.info Data; do
        [ -e "$src/$f" ] || { echo "missing $src/$f"; exit 1; }
    done
    tmp="$dst.partial"
    rm -rf "$tmp"
    # -c clones on APFS, so the 5 GB of game data takes no extra disk space.
    cp -Rc "$src" "$tmp" 2>/dev/null || { rm -rf "$tmp"; cp -R "$src" "$tmp"; }
    find "$tmp" -name "*.app" -prune -exec rm -rf {} +
    python3 -I "$(dirname "$0")/../tools/sc_mac_to_windows.py" "$tmp"
    mv "$tmp" "$dst"
else
    for f in x86/StarCraft.exe x86/ClientSdk.dll x86_64/StarCraft.exe Data; do
        [ -e "$src/$f" ] || { echo "missing $src/$f"; exit 1; }
    done
    mv "$src" "$dst"
fi

# Shortcut to the game's Documents folder (settings, maps, replays) at ~/Games/StarCraft.
mkdir -p "$DRIVE_C/users/Sikarugir/Documents/StarCraft/Maps/Replays" "$HOME/Games"
[ -e "$HOME/Games/StarCraft" ] || ln -s "$DRIVE_C/users/Sikarugir/Documents/StarCraft" "$HOME/Games/StarCraft"
echo "Game installed at $dst"

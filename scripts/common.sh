# Shared helpers. Source this from the other scripts.
WRAPPER="${WRAPPER:-$HOME/Applications/Sikarugir/ShieldBattery.app}"
C="$WRAPPER/Contents"
PREFIX="$C/SharedSupport/prefix"
DRIVE_C="$PREFIX/drive_c"
PLIST="$C/Info.plist"
SB_DIST="$DRIVE_C/users/Sikarugir/AppData/Local/Programs/shieldbattery-app/resources/game/dist"

# Run a Windows exe/bat inside the wrapper. The launcher sets up the Wine env that a
# bare `wine` call lacks. Arguments after the path are dropped when Wine is already
# running ("secondary run"), so put arguments in a .bat file instead.
wrun() { (cd "$HOME" && "$C/MacOS/wineskinlauncher" "$@"); }

# Run a .bat in C:\sbtools and wait until it has finished. The launcher can return before the
# .bat runs, and a wkill right after that loses its registry changes.
wrun_bat() {
    local done="$DRIVE_C/sbtools/bat.done"
    rm -f "$done"
    printf 'echo done> C:\\sbtools\\bat.done\r\n' >> "$1"
    wrun "$1" >/dev/null 2>&1
    for _ in $(seq 90); do [ -f "$done" ] && return 0; sleep 1; done
    echo "timed out waiting for $1 to run" >&2
    return 1
}

# Stop every Wine process in the wrapper, ShieldBattery included.
wkill() {
    pkill -f "ShieldBattery.exe" 2>/dev/null || true
    sleep 2
    DYLD_FALLBACK_LIBRARY_PATH="$C/Frameworks:/usr/lib" WINEPREFIX="$PREFIX" \
        "$C/SharedSupport/wine/bin/wineserver" -k 2>/dev/null || true
    sleep 1
}

plist_set() { /usr/libexec/PlistBuddy -c "Set :'$1' '$2'" "$PLIST"; }

# ShieldBattery on macOS (Apple Silicon)

Run [ShieldBattery](https://shieldbattery.net), the community ladder client for StarCraft:
Remastered, on an Apple Silicon Mac using Wine. Online games against other players and HD
graphics both work.

Unofficial and not affiliated with ShieldBattery or Blizzard. ShieldBattery only supports
Windows; you use this at your own risk.

**Tested on** an M5 Pro running macOS 26.4, ShieldBattery 12.2.1 and 12.3.0, and StarCraft: Remastered build 13515.

| Feature | Status |
|---|---|
| ShieldBattery client (login, chat, lobbies, maps) | works |
| Games against the computer | works |
| Online games against other players | works (needs patch 2) |
| HD graphics and skins | works if you own them (see [HD graphics](#hd-graphics-optional)) |
| Replays | work |

## How it works

ShieldBattery is a Windows app that launches the **Windows** build of StarCraft: Remastered
and injects its own code into it, so the native Mac version of the game can't be used. Both run
inside a [Sikarugir](https://github.com/Sikarugir-App/Sikarugir) Wine wrapper, with DXMT
translating Direct3D 11 to Metal. Battle.net isn't needed: ShieldBattery starts the game
directly.

Two bugs stop ShieldBattery from working under Wine on macOS. `scripts/patch_shieldbattery_wine.py`
patches both in ShieldBattery's game DLLs; [What gets patched](#what-gets-patched) explains them.

## Requirements

- An Apple Silicon Mac with [Rosetta 2](https://support.apple.com/en-us/102527) installed
  (`softwareupdate --install-rosetta`) and [Homebrew](https://brew.sh).
- StarCraft: Remastered (the free edition is enough), either:
  - the **macOS** game installed with Battle.net (e.g. `/Applications/StarCraft`), or
  - the whole `StarCraft` folder copied from a **Windows** install (it has `x86\`, `x86_64\` and
    `Data\`, about 5.5 GB).
- A ShieldBattery account.
- Python 3 (comes with the Xcode Command Line Tools).

## Setup

Clone this repo and run the scripts from its root. By default the wrapper goes to
`~/Applications/Sikarugir/ShieldBattery.app`; set `WRAPPER=/other/path.app` to change that.

**1. Build the Wine wrapper** (downloads about 270 MB):

```bash
./scripts/1-build-wrapper.sh
```

This downloads the Sikarugir wrapper template and a Wine 11 engine and creates a Windows 10
prefix. You don't need the Sikarugir Creator app.

**2. Add the game files:**

```bash
./scripts/2-install-game.sh /path/to/StarCraft
```

A Windows folder is moved to `C:\Program Files (x86)\StarCraft`, where ShieldBattery looks by
default. A macOS install is copied there instead (an APFS clone, so no extra disk space) and
gets the Windows executables for the same game version from Blizzard's CDN (about 130 MB);
the Mac game keeps working. The copy never updates itself: when a new StarCraft patch is out,
update the Mac game in Battle.net, delete `C:\Program Files (x86)\StarCraft` and run this step
again. The script also creates `~/Games/StarCraft`, a shortcut to the game's settings, maps
and replays.

**3. Install ShieldBattery.** Download the installer from
[shieldbattery.net](https://shieldbattery.net) in your browser, then:

```bash
./scripts/3-install-shieldbattery.sh ~/Downloads/ShieldBattery-setup-*.exe
```

This installs it silently, applies the patches and sets the wrapper to open ShieldBattery.

**4. Play:** open `~/Applications/Sikarugir/ShieldBattery.app` and log in.

### Updating ShieldBattery

ShieldBattery's auto-updater **can't work under Wine**. It downloads the update, then tries to
check the installer's signature with PowerShell, which Wine only provides as an empty stub. The
log shows `Error downloading update: SyntaxError: Unexpected end of JSON input`, and you're
stuck on the old version. To update, install the new version by hand over the old one (your
login and settings are kept), which also re-applies the patches:

1. Find the current version on line 1 of <https://cdn.shieldbattery.net/app/latest.yml>.
2. Download `https://cdn.shieldbattery.net/app/ShieldBattery-setup-<version>.exe`. Optionally,
   compare its SHA-512 (`shasum -a 512 file | cut -d' ' -f1 | xxd -r -p | base64`) with
   the one in `latest.yml`.
3. Run `./scripts/3-install-shieldbattery.sh ShieldBattery-setup-<version>.exe`.

If games stick at "Launching game…" or online games fail, the patches are probably missing.
Re-run them (safe to run any time):

```bash
python3 scripts/patch_shieldbattery_wine.py
```

## Hotkeys and other game settings

ShieldBattery has no hotkey editor: the game gets your hotkeys (and any setting ShieldBattery
doesn't manage itself) from Blizzard's `Documents\StarCraft\CSettings.json`, with
ShieldBattery's own settings laid over it. A fresh prefix has no such file. To use the hotkeys
from the Mac game, copy its settings file in, then quit and reopen ShieldBattery (it reads the
file at startup):

```bash
cp ~/Library/Application\ Support/Blizzard/StarCraft/CSettings.json \
   ~/Applications/Sikarugir/ShieldBattery.app/Contents/SharedSupport/prefix/drive_c/users/Sikarugir/Documents/StarCraft/
```

Copy it again after changing hotkeys in the Mac game. The file has the same format on both
platforms.

## HD graphics (optional)

There are no HD files to install: the HD graphics, Carbot skin and HD shaders are already in
the game's `Data\` folder (free edition included), which step 2 put in place. What's missing
is the license that unlocks them. HD graphics and skins you've bought are read from Battle.net's offline license file,
`cookie.bin`, which is encrypted for the machine it was written on. Take it either from this
Mac's own Battle.net or from a Windows PC.

### From the Mac's Battle.net

Log in to Battle.net for macOS and start StarCraft: Remastered from it once, so it writes
`~/Library/Application Support/Blizzard Entertainment/ClientSdk/cookie.bin`. Then:

```bash
./scripts/4-set-hd-from-mac.sh
```

This copies the cookie into the prefix unchanged and gives the prefix a MachineGuid and C:
volume serial from which the Windows game derives this Mac's key (see
[How the cookie is encrypted](#how-the-cookie-is-encrypted)). The MachineGuid ends in a few odd
characters and the serial is a single digit, like `00000001`; that's expected. It quits
ShieldBattery if it's running. Run it again whenever HD stops working: after a new cookie, or
after macOS changes the Wi-Fi address, which is part of the Mac key.

This works only when the Wi-Fi MAC address ends in a byte from `30` to `39` (an ASCII digit),
because that byte has to become the volume serial. The script says so if yours doesn't. With a
rotating private Wi-Fi address you can wait for a matching one; otherwise use a Windows cookie.

ShieldBattery logs this cookie as `invalid (doesn't match this machine, or corrupt)` in
`game.0.log`, because it reads MachineGuid differently from the game. The game still uses it.

### From a Windows PC

Copy `cookie.bin` from a Windows PC where you've played SC:R through Battle.net, and make
the Wine prefix look like that PC. The file is encrypted with a key derived from the PC's
**MachineGuid** and the **volume serial number** of the drive the game is installed on.

You need three things from the Windows PC:

| What | Where |
|---|---|
| `cookie.bin` | `%LOCALAPPDATA%\Blizzard Entertainment\ClientSdk\cookie.bin` |
| MachineGuid | in PowerShell: `(Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Cryptography).MachineGuid` |
| Volume serial | `vol C:` (or the game's drive letter) prints e.g. `1A2B-3C4D`; use `1a2b3c4d` |

If you only have the Windows disk and not a running Windows, `tools/hive_guid.py` reads the
MachineGuid from `Windows/System32/config/SOFTWARE`. On Linux, the volume serial is the last
8 hex digits of the NTFS partition's UUID (`lsblk -o NAME,UUID`).

Check that the three match before changing anything. The script prints `MATCH` for the
correct serial:

```bash
python3 tools/cookie_check.py cookie.bin <MachineGuid> $((16#1a2b3c4d))
```

Then install them into the prefix. This quits ShieldBattery if it's running:

```bash
./scripts/4-set-hd-identity.sh cookie.bin <MachineGuid> 1a2b3c4d
```

The cookie works even after its expiry date, because ShieldBattery handles that itself. If HD
stops working, play once through Battle.net on Windows and copy the new `cookie.bin`.

### How the cookie is encrypted

Each game's entry holds `EFC22400 | salt (10 bytes) | tag (20 bytes) | ciphertext`. The key
material is PBKDF2-HMAC-SHA512 over a password and the salt, 8192 iterations, 80 bytes: bytes
0–31 are a Serpent key, 32–63 an HMAC-SHA512 key (the tag is the first 20 bytes), 64–79 the IV
for Serpent in big-endian CTR mode (Botan's `Serpent/CTR-BE`). The password is
`base64(SHA1(x))`:

- **Windows:** `x` is the MachineGuid followed by the decimal volume serial.
- **macOS:** `x` is the IOPlatformUUID followed by the 6 raw bytes of the MAC address of the
  first non-loopback network interface, usually `en0` (Wi-Fi). With a private Wi-Fi address,
  that's the private address in use, not the hardware one.

The plaintext lists your licenses (`hd`, `sc-carbot`, ...). The 256-byte field next to the entry
looks like a Blizzard signature over the encrypted payload: a cookie re-encrypted for another
identity was reported valid by ShieldBattery, but the game ignored its licenses, while the same
cookie left unchanged worked. So the prefix has to reproduce the original key instead.

The game reads MachineGuid and turns it into bytes with the ANSI code page (1252 in an en-US
prefix). So the Mac's `x` can be reproduced: MachineGuid is `x` without its last byte, read as
code page 1252, and the volume serial is that last byte as a digit. `tools/mac_cookie_identity.py`
finds the right MAC address and writes the MachineGuid as a `.reg` file. Some macOS processes,
Homebrew's Python among them, see every MAC address as `02:00:00:00:00:00`, so the script reads
them with `ifconfig` and passes them in.

## What gets patched

### 1. `sb_init_64.dll` won't load: the game hangs at "Launching game…"

The game log (see [Troubleshooting](#troubleshooting)) shows
`Unable to load sb_init.dll: Os { code: 1114 }`. That DLL's entry point is a single `ret`
instruction, so whether it loads depends on whatever happens to be in a CPU register. Windows
leaves a non-zero value there, so it loads by luck; Wine leaves 0, so it fails. The patch
sets the entry point to 0, which means "no entry point". This affects Wine on Linux too.

### 2. Online games: `binding the client UDP socket failed (os error 10022)`

ShieldBattery's online code opens an IPv6 socket that also carries IPv4 traffic, and tries to
set two IPv4-only options on it (`IP_DONTFRAGMENT`, `IP_PKTINFO`). Linux accepts that, but
**macOS rejects it** and Wine reports the error as `WSAEINVAL` (10022). The networking library
only skips the error codes for "not supported", so the connection fails. The patch makes it
skip 10022 at those two places too, so both options are left off and the connection
works normally. The test programs in `tools/winsock-tests/` show the failing calls and the
working IPv4 round trip.

The patcher finds both places by byte pattern rather than fixed addresses, so it should
keep working across ShieldBattery updates. It refuses to patch anything it doesn't recognise
and keeps the originals as `*.orig`. Draft reports for the projects involved are in
[`docs/upstream-issues.md`](docs/upstream-issues.md).

## Troubleshooting

- **Logs:** inside the wrapper at
  `Contents/SharedSupport/prefix/drive_c/users/Sikarugir/AppData/Roaming/ShieldBattery/logs/`:
  `app.0.log` for the client, `game.0.log` for the game.
- **Replays don't show up:** put them in `~/Games/StarCraft/Maps/Replays`. The wrapper keeps
  the Windows Documents folder inside itself on purpose: macOS blocks Finder-launched Wine apps
  from `~/Documents`, which empties ShieldBattery's replay list. So **deleting the
  wrapper also deletes your replays and settings.**
- **Don't switch the renderer to D3DMetal.** It turns the ShieldBattery window black, and the
  `--disable-gpu` flags don't fix that. The default DXMT handles both the app and the game, HD
  included.
- **A game occasionally exits with code `0x80000101`** and no crash dump. Trying again works.
  The code is Wine's `EXCEPTION_WINE_ASSERTION`: a Wine trace shows the process aborting on
  `-[NSIndirectTaggedPointerString newComputePipelineStateWithDescriptor:options:reflection:error:]:
  unrecognized selector`: DXMT used its Metal device before initializing it, so whether the
  game survives depends on leftover memory. DXMT fixed it upstream in commit
  [`fb45156`](https://github.com/3Shain/dxmt/commit/fb4515681daefb789a4d0f403c4bdbca88f3b3de),
  after the template's build (`v0.80-244-g7c8dee1`). Upstream builds can't simply replace the
  template's, though: they lack its `DXMT_ALLOW_CROSS_PROCESS_SWAPCHAIN` change, and without it
  the ShieldBattery window stays invisible. So `scripts/patch_dxmt.py` applies the same fix to
  the template's `d3d11.dll` (step 1 runs it; originals are kept as `d3d11.dll.orig`). For a
  wrapper built before that:

  ```bash
  W=~/Applications/Sikarugir/ShieldBattery.app/Contents/SharedSupport
  python3 scripts/patch_dxmt.py "$W/renderer/dxmt/wine/x86_64-windows/d3d11.dll" \
      "$W/prefix/drive_c/windows/system32/d3d11.dll"
  ```

  To capture a Wine trace, set
  `Debug Mode` to `1` and `WINEDEBUG` to `-plugplay,+seh,+loaddll` in the wrapper's
  `Contents/Info.plist`. The trace is written to `Contents/SharedSupport/Logs/LastRunWine.log`
  (about 30 MB per game, and it slows the game down).
- **Running Windows programs in the wrapper:** a plain `wine` command doesn't work here. Use
  `Contents/MacOS/wineskinlauncher /path/to/file.exe` (`wrun` in `scripts/common.sh`). Arguments
  are dropped when Wine is already running, so put commands with arguments in a `.bat` file.
- **Rosetta:** Wine runs through Rosetta 2. Apple keeps it fully available through macOS 27 and
  plans to limit it afterwards, so this setup may need an Apple Silicon-native Wine eventually.

## Repository layout

| Path | Purpose |
|---|---|
| `scripts/1-build-wrapper.sh` … `4-set-hd-identity.sh` | Setup steps (`4-set-hd-from-mac.sh` is the Mac alternative to step 4) |
| `scripts/common.sh` | Wrapper paths and helpers (`wrun`, `wkill`) |
| `scripts/patch_shieldbattery_wine.py` | The two DLL patches |
| `scripts/patch_dxmt.py` | Fixes DXMT's random crash at game start (`0x80000101`) |
| `tools/sc_mac_to_windows.py` | Downloads the Windows executables into a macOS StarCraft folder |
| `tools/mac_cookie_identity.py` | Finds the MachineGuid and volume serial that open a macOS Battle.net `cookie.bin` |
| `tools/cookie_check.py` | Checks a `cookie.bin` against a MachineGuid and volume serial |
| `tools/hive_guid.py` | Reads the MachineGuid from an offline Windows registry file |
| `tools/winsock-tests/` | Small Windows test programs; build with `brew install mingw-w64`, then `x86_64-w64-mingw32-gcc x.c -lws2_32` |
| `docs/upstream-issues.md` | Bug write-ups for ShieldBattery and rally-point2 / noq-udp |

"""Install winemetal_leakfix.m in front of DXMT's winemetal.so (see that file for the leaks).

The real library is renamed winemetal.orig.so and the compiled stand-in takes its name. Before
the first install this checks that the binary's call tables have the expected size and that the
two slots the stand-in changes hold the functions it expects. Re-running rebuilds the stand-in.
Needs the Xcode Command Line Tools (clang).

Usage: patch_winemetal.py <dir with winemetal.so>   (renderer/dxmt/wine/x86_64-unix)
"""
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE_SIZE, SLOT_DESC, SLOT_QUERY = 146, 96, 101


def segments(data):
    ncmds, off, segs = struct.unpack_from("<I", data, 16)[0], 32, []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            segs.append(struct.unpack_from("<QQQ", data, off + 24))  # vmaddr, vmsize, fileoff
        off += size
    return segs


def file_offset(segs, addr):
    for vm, vs, fo in segs:
        if vm <= addr < vm + vs:
            return addr - vm + fo
    raise ValueError(hex(addr))


def disasm(path, start, length):
    return subprocess.run(["xcrun", "llvm-objdump", "-d", "--no-show-raw-insn", f"--start-address={start}",
                           f"--stop-address={start + length}", path], capture_output=True, text=True,
                          check=True).stdout


def check(path):
    data = open(path, "rb").read()
    segs = segments(data)
    syms = dict((name, int(addr, 16)) for addr, name in re.findall(
        r"^([0-9a-f]+) D (___wine_unix_call_(?:wow64_)?funcs)$",
        subprocess.run(["nm", path], capture_output=True, text=True, check=True).stdout, re.M))
    funcs, wow64 = syms["___wine_unix_call_funcs"], syms["___wine_unix_call_wow64_funcs"]
    if (wow64 - funcs) // 8 != TABLE_SIZE:
        return f"call table has {(wow64 - funcs) // 8} entries, expected {TABLE_SIZE}"
    # Table entries are chained-fixup rebases; the low 36 bits are the target offset.
    entry = lambda table, i: struct.unpack_from("<Q", data, file_offset(segs, table + 8 * i))[0] & 0xFFFFFFFFF
    for table in (funcs, wow64):
        desc = disasm(path, entry(table, SLOT_DESC), 0x60)
        if desc.count("<_GetDisplayColorGamut>") != 2 or "<_GetNSScreenForDisplayID>" not in desc:
            return f"slot {SLOT_DESC} isn't _WMTGetDisplayDescription"
        query = disasm(path, entry(table, SLOT_QUERY), 0x190)
        sels = set()
        for addr in re.findall(r"## (0x[0-9a-f]+)", query):
            try:
                target = struct.unpack_from("<Q", data, file_offset(segs, int(addr, 16)))[0] & 0xFFFFFFFFF
                o = file_offset(segs, target)
                sels.add(data[o:data.index(b"\0", o)].decode("latin-1"))
            except (ValueError, struct.error):
                pass
        if not {"delegate", "window", "screen", "deviceDescription"} <= sels:
            return f"slot {SLOT_QUERY} isn't _WMTQueryDisplaySettingForLayer"
    return None


libdir = sys.argv[1]
lib, orig = os.path.join(libdir, "winemetal.so"), os.path.join(libdir, "winemetal.orig.so")
if not os.path.exists(orig):
    problem = check(lib)
    if problem:
        raise SystemExit(f"{lib}: not patched, {problem} (a different DXMT build, needs a look)")
    os.rename(lib, orig)
built = lib + ".tmp"
# The original links @rpath/winemac.so and @rpath/ntdll.so, which are in Wine's folder. dlopen also
# searches its caller's rpaths, so the stand-in needs this to load the original.
subprocess.run(["xcrun", "clang", "-arch", "x86_64", "-mmacosx-version-min=11.0", "-O2", "-dynamiclib",
                "-install_name", "@rpath/winemetal_leakfix.so", "-framework", "AppKit", "-framework", "ColorSync",
                "-Wl,-rpath,@loader_path/../../../../wine/lib/wine/x86_64-unix",
                "-o", built, os.path.join(HERE, "winemetal_leakfix.m")], check=True)
os.replace(built, lib)
print(f"{lib}: leak fix installed (original kept as winemetal.orig.so)")

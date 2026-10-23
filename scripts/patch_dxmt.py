"""Patch the Sikarugir template's DXMT d3d11.dll so games don't randomly die at start.

DXMT's ArgumentEncodingContext constructor builds ClearUAV, whose constructor creates compute
pipelines through getComputePipeline(), which reads the context's device_ member. device_ is
only stored at the end of the constructor, so the pipeline is created on whatever that memory
held: the process aborts with "-[NSIndirectTaggedPointerString
newComputePipelineStateWithDescriptor:options:reflection:error:]: unrecognized selector", which
Wine reports as exit code 0x80000101. Fixed upstream in DXMT fb45156 by initializing device_
first, but upstream builds lack the template's DXMT_ALLOW_CROSS_PROCESS_SWAPCHAIN change, without
which ShieldBattery's window stays invisible, so the template's own build is patched instead.

Fix: the constructor's `mov [rcx+8], r9; lea r14, [rcx+0x10]` (8 bytes, right after the
prologue) becomes a jump to a stub in .text's padding that does the same and also stores the
device argument (r8) into device_, then jumps back. device_'s offset is read from the
constructor's own late `mov [r13+device_], rbp; mov [r13+device_+8], rdi`.

Usage: patch_dxmt.py d3d11.dll...   (the x86_64 build; originals are kept as <name>.orig)
"""
import os
import re
import shutil
import struct
import sys

PROLOGUE = bytes.fromhex("4c89ce4c89c54889d74989cd")  # mov rsi,r9; mov rbp,r8; mov rdi,rdx; mov r13,rcx
HOOKED = bytes.fromhex("4c8949084c8d7110")  # mov [rcx+8],r9; lea r14,[rcx+0x10]
AFTER = bytes.fromhex("4c89f14c89c24d89c84d89e9e8")  # mov rcx,r14; ...; call EmulatedCommandContext
LATE_STORE = re.compile(rb"\x49\x89\xad(....)\x49\x89\xbd(....)", re.S)  # mov [r13+X],rbp; mov [r13+X+8],rdi


def text_section(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0"
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    sec = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
    for i in range(nsec):
        hdr = sec + i * 40
        if data[hdr:hdr + 8].rstrip(b"\0") == b".text":
            vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, hdr + 8)
            return hdr, vsize, va, raw_size, raw_ptr
    raise SystemExit("no .text section")


def patch(path):
    if not os.path.exists(path):
        return "not there, skipped"
    data = bytearray(open(path, "rb").read())
    hdr, vsize, va, raw_size, raw_ptr = text_section(data)
    rva = lambda off: off - raw_ptr + va
    sites = [m.start() for m in re.finditer(re.escape(PROLOGUE + HOOKED + AFTER), data)]
    if not sites:
        if [m.start() for m in re.finditer(re.escape(PROLOGUE), data)]:
            return "already patched or a different DXMT build - check by hand"
        return "SKIPPED: constructor not found - different DXMT build, needs a look"
    if len(sites) > 1:
        return f"SKIPPED: constructor pattern found {len(sites)} times"
    hook = sites[0] + len(PROLOGUE)
    late = [m for m in LATE_STORE.finditer(data, hook, hook + 0x2000)
            if struct.unpack("<I", m.group(2))[0] == struct.unpack("<I", m.group(1))[0] + 8]
    if len(late) != 1:
        return "SKIPPED: device_ store not found"
    device_off = struct.unpack("<I", late[0].group(1))[0]

    # The stub goes 16-aligned after .text's used bytes, in the 0xCC padding before raw_size.
    cave = raw_ptr + ((vsize + 15) & ~15)
    stub_len = len(HOOKED) + 7 + 5
    if cave + stub_len > raw_ptr + raw_size or set(data[cave:cave + stub_len]) != {0xCC}:
        return "SKIPPED: no free padding at the end of .text"
    back = hook + len(HOOKED)
    stub = HOOKED + b"\x4c\x89\x81" + struct.pack("<I", device_off)  # mov [rcx+device_], r8
    stub += b"\xe9" + struct.pack("<i", rva(back) - (rva(cave) + len(stub) + 5))
    data[cave:cave + len(stub)] = stub
    data[hook:hook + 8] = b"\xe9" + struct.pack("<i", rva(cave) - (rva(hook) + 5)) + b"\x90" * 3
    struct.pack_into("<I", data, hdr + 8, cave + len(stub) - raw_ptr)  # cover the stub in VirtualSize

    shutil.copy2(path, path + ".orig")
    open(path, "wb").write(data)
    return f"patched (device_ at +0x{device_off:x}, stub at RVA 0x{rva(cave):x})"


for p in sys.argv[1:]:
    print(f"{p}: {patch(p)}")

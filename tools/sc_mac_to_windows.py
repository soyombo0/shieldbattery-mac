"""Turn a macOS StarCraft: Remastered folder into a Windows one.

The game data (Data/, a CASC store) is the same on both platforms; only the executables
differ. This downloads the Windows files (x86/, x86_64/, locales/*.dll, ...) for the exact
build in .build.info from Blizzard's CDN, checks each against its MD5, and retags
.build.info for Windows.

Usage: sc_mac_to_windows.py /path/to/StarCraft
"""
import hashlib, os, struct, sys, urllib.request, zlib

root = sys.argv[1]


def read_build_info(path):
    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if l]
    cols = [c.split("!")[0] for c in lines[0].split("|")]
    rows = [dict(zip(cols, l.split("|"))) for l in lines[1:]]
    return cols, rows


cols, rows = read_build_info(os.path.join(root, ".build.info"))
info = next(r for r in rows if r["Active"] == "1")
hosts = info["CDN Hosts"].split()


def cdn(kind, key, suffix="", rng=None):
    path = f"{info['CDN Path']}/{kind}/{key[:2]}/{key[2:4]}/{key}{suffix}"
    for host in hosts:
        req = urllib.request.Request(f"http://{host}/{path}")
        if rng:
            req.add_header("Range", f"bytes={rng[0]}-{rng[0] + rng[1] - 1}")
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except OSError as e:
            err = e
    raise SystemExit(f"download failed: {path}: {err}")


def blte(d):
    assert d[:4] == b"BLTE"
    hsize = struct.unpack_from(">I", d, 4)[0]
    if hsize == 0:
        chunks, pos = [len(d) - 8], 8
    else:
        n = int.from_bytes(d[9:12], "big")
        chunks, pos = [struct.unpack_from(">I", d, 12 + i * 24)[0] for i in range(n)], hsize
    out = bytearray()
    for size in chunks:
        c = d[pos:pos + size]
        pos += size
        if c[:1] == b"N":
            out += c[1:]
        elif c[:1] == b"Z":
            out += zlib.decompress(c[1:])
        else:
            raise SystemExit(f"unsupported BLTE chunk mode {c[:1]!r}")
    return bytes(out)


def config(key):
    return dict(l.split(" = ", 1) for l in cdn("config", key).decode().splitlines() if " = " in l)


def archive_index(d):
    """Map ekey -> (size, offset) from a CDN .index file."""
    f = d[-28:]
    block, osize, ssize, ksize = f[11] * 1024, f[12], f[13], f[14]
    count = struct.unpack_from("<I", f, 16)[0]
    esize = ksize + ssize + osize
    out, pos = {}, 0
    while len(out) < count:
        b, pos = d[pos:pos + block], pos + block
        for q in range(0, len(b) - esize + 1, esize):
            if not any(b[q:q + ksize]):
                break
            size = int.from_bytes(b[q + ksize:q + ksize + ssize], "big")
            off = int.from_bytes(b[q + ksize + ssize:q + esize], "big")
            out[b[q:q + ksize].hex()] = (size, off)
    return out


build, cdncfg = config(info["Build Key"]), config(info["CDN Key"])

# Install manifest: every loose file of the game, with platform/arch/locale tags.
inst = blte(cdn("data", build["install"].split()[1]))
assert inst[:2] == b"IN"
hsize = inst[3]
ntags, nfiles = struct.unpack_from(">HI", inst, 4)
pos, masklen, tags = 10, (nfiles + 7) // 8, []
for _ in range(ntags):
    end = inst.index(b"\0", pos)
    ttype = struct.unpack_from(">H", inst, end + 1)[0]
    tags.append((inst[pos:end].decode(), ttype, inst[end + 3:end + 3 + masklen]))
    pos = end + 3 + masklen
files = []
for i in range(nfiles):
    end = inst.index(b"\0", pos)
    name, ckey = inst[pos:end].decode(), inst[end + 1:end + 1 + hsize].hex()
    pos = end + 5 + hsize
    files.append((name, ckey, {t for t, _, m in tags if m[i // 8] & (0x80 >> (i % 8))}))

# Same tags as the Mac install (locale, igr/noigr), with Windows x86_64 instead of OSX.
names = {t for t, _, _ in tags}
want = {t for t in info["Tags"].split(":")[0].split() if t in names and t != "OSX"} | {"Windows", "x86_64"}
by_type = {}
for t, ttype, _ in tags:
    if t in want:
        by_type.setdefault(ttype, set()).add(t)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


todo = []
for name, ckey, ftags in files:
    if all(ftags & s for s in by_type.values()):
        path = os.path.join(root, *name.split("/"))
        if not (os.path.isfile(path) and md5(path) == ckey):
            todo.append((name, ckey, path))
print(f"{len(todo)} Windows files to download")

# Encoding file: content key -> encoded key (the name the CDN stores it under).
enc = blte(cdn("data", build["encoding"].split()[1]))
assert enc[:2] == b"EN"
ch, eh = enc[3], enc[4]
psize = struct.unpack_from(">H", enc, 5)[0] * 1024
npages = struct.unpack_from(">I", enc, 9)[0]
pos, wanted, c2e = 22 + struct.unpack_from(">I", enc, 18)[0] + npages * 32, {c for _, c, _ in todo}, {}
for _ in range(npages):
    page, pos = enc[pos:pos + psize], pos + psize
    q = 0
    while q + 6 + ch <= len(page) and page[q]:
        ckey = page[q + 6:q + 6 + ch].hex()
        if ckey in wanted:
            c2e[ckey] = page[q + 6 + ch:q + 6 + ch + eh].hex()
        q += 6 + ch + page[q] * eh

# Where each encoded file lives: inside an archive, or loose on the CDN.
need, where = set(c2e.values()), {}
for a in cdncfg["archives"].split():
    for ekey, loc in archive_index(cdn("data", a, ".index")).items():
        if ekey in need:
            where[ekey] = (a, loc)

for n, (name, ckey, path) in enumerate(todo, 1):
    ekey = c2e[ckey]
    if ekey in where:
        a, (size, off) = where[ekey]
        data = blte(cdn("data", a, rng=(off, size)))
    else:
        data = blte(cdn("data", ekey))
    if hashlib.md5(data).hexdigest() != ckey:
        raise SystemExit(f"checksum mismatch: {name}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    print(f"[{n}/{len(todo)}] {name}")

# Retag .build.info so the game sees a Windows install.
lines = open(os.path.join(root, ".build.info"), encoding="utf-8").read().splitlines()
ti = cols.index("Tags")
for i, l in enumerate(lines[1:], 1):
    if l:
        f = l.split("|")
        f[ti] = f[ti].replace("OSX ", "Windows x86_64 ")
        lines[i] = "|".join(f)
with open(os.path.join(root, ".build.info"), "w", encoding="utf-8") as out:
    out.write("\n".join(lines) + "\n")
print("done")

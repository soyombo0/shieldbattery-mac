"""Find the Windows identity (MachineGuid, volume serial) under which a macOS Battle.net
cookie.bin opens unchanged in Windows StarCraft: Remastered.

The SC:R entry is keyed with base64(SHA1(x)). On macOS, x is the IOPlatformUUID followed by the
6 raw MAC bytes of the first non-loopback network interface; on Windows it's MachineGuid,
converted with the ANSI code page, followed by the decimal volume serial. The cookie can't be
re-encrypted for another identity (the game also checks a Blizzard signature over the encrypted
payload), so the Windows side is made to produce the Mac's x instead: MachineGuid is x minus its
last byte, decoded as code page 1252 (the prefix's en-US ANSI code page), and the serial is the
last byte, which therefore has to be an ASCII digit.

Usage: mac_cookie_identity.py <mac cookie.bin> <out.reg> <IOPlatformUUID> <mac>...
  Every MAC address given (aa:bb:cc:dd:ee:ff) is tried; the one that authenticates is used.
  Writes a .reg file setting MachineGuid and prints the volume serial in hex.
"""
import base64, hashlib, hmac, sys

SC_R = 21297


def fields(buf):
    i = 0
    while i < len(buf):
        def varint():
            nonlocal i
            v = s = 0
            while True:
                b = buf[i]; i += 1
                v |= (b & 0x7F) << s; s += 7
                if b < 0x80: return v
        key = varint(); f, wt = key >> 3, key & 7
        if wt == 0: yield f, varint()
        elif wt == 2:
            n = varint(); yield f, buf[i:i + n]; i += n
        else: raise ValueError(wt)


def opens(payload, x):
    salt, mac, ct = payload[4:14], payload[14:34], payload[34:]
    hwid = base64.b64encode(hashlib.sha1(x).digest())
    keys = hashlib.pbkdf2_hmac("sha512", hwid, salt, 8192, 80)
    return hmac.new(keys[32:64], ct, hashlib.sha512).digest()[:20] == mac


src, reg_path, uuid, *macs = sys.argv[1:]
entries = [dict(fields(v)) for f, v in fields(open(src, "rb").read()) if f == 5]
entry = next((e for e in entries if e.get(4) == SC_R), None)
if entry is None:
    raise SystemExit("no StarCraft: Remastered entry in the cookie")
payload = base64.b64decode(entry[2])
assert payload[:4] == bytes.fromhex("EFC22400"), payload[:4].hex()

for m in macs:
    x = uuid.encode() + bytes.fromhex(m.replace(":", ""))
    if opens(payload, x):
        print(f"Mac cookie opens with UUID {uuid} and MAC {m}", file=sys.stderr)
        break
else:
    raise SystemExit("none of the MAC addresses opens the cookie; start SC:R from Battle.net on this Mac and retry")

if not 0x30 <= x[-1] <= 0x39:
    raise SystemExit(f"MAC {m} doesn't end in a byte that is an ASCII digit (30-39 hex), so no Windows "
                     "volume serial can reproduce it. Use a Windows cookie instead (see README).")
if 0 in x[:-1]:
    raise SystemExit(f"MAC {m} contains a 00 byte, which a registry string can't hold")
# Code page 1252 leaves 81, 8D, 8F, 90 and 9D undefined; Windows and Wine map them to U+0081 etc.
guid = "".join(chr(b) if b in (0x81, 0x8D, 0x8F, 0x90, 0x9D) else bytes([b]).decode("cp1252") for b in x[:-1])
data = (guid + "\0").encode("utf-16-le")
with open(reg_path, "w", encoding="utf-16") as out:
    out.write("Windows Registry Editor Version 5.00\r\n\r\n"
              "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography]\r\n"
              f"\"MachineGuid\"=hex(1):{','.join(f'{b:02x}' for b in data)}\r\n")
print(f"{x[-1] - 0x30:08x}")

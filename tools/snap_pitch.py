"""One-shot float-diff to find the camera-pitch register.

Usage:
  py tools/snap_pitch.py up      # hold camera pitched fully UP, then run
  py tools/snap_pitch.py down    # hold camera pitched fully DOWN, then run
  py tools/snap_pitch.py diff    # compare up vs down, print candidates

Reads the 4 KB camera-config region (0x0106A000..0x0106E000) as floats
and caches to JSON. The diff step prints float addresses whose value
differs by a plausible pitch delta (~0.5..2.0 rad).
"""
import json, os, struct, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

OUT = Path(__file__).resolve().parent.parent / "archive" / "scenarios"
BASE = 0x0106A000
SIZE = 0x4000  # 16 KB to be safe

def snap(label):
    with PineClient() as pc:
        buf = pc.read_bytes(BASE, SIZE)
    vals = {}
    for off in range(0, SIZE, 4):
        v = struct.unpack_from('<I', buf, off)[0]
        vals[f"0x{BASE + off:08X}"] = v
    path = OUT / f"pitch_{label}.json"
    with path.open('w') as f:
        json.dump(vals, f)
    print(f"[*] Snapped {label} -> {path}")

def diff():
    with (OUT / "pitch_up.json").open() as f: u = json.load(f)
    with (OUT / "pitch_down.json").open() as f: d = json.load(f)
    cands = []
    for k, vu in u.items():
        vd = d[k]
        if vu == vd:
            continue
        fu = struct.unpack('<f', struct.pack('<I', vu))[0]
        fd = struct.unpack('<f', struct.pack('<I', vd))[0]
        # Float sanity: finite, plausible angle range
        try:
            delta = fu - fd
        except Exception:
            continue
        if not (-10 < fu < 10) or not (-10 < fd < 10):
            continue
        if abs(delta) < 0.1:
            continue
        cands.append((int(k, 16), vu, vd, fu, fd, abs(delta)))
    cands.sort(key=lambda c: -c[5])
    print(f"[*] {len(cands)} float diffs with |delta| >= 0.1 in plausible angle range")
    for a, vu, vd, fu, fd, delta in cands[:40]:
        print(f"  0x{a:08X}  up={fu:+.4f} ({vu:08X})  down={fd:+.4f} ({vd:08X})  delta={delta:+.4f}")

if __name__ == "__main__":
    if sys.argv[1] == "diff":
        diff()
    else:
        snap(sys.argv[1])

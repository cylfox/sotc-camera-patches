"""High-rate poll of 10 candidate float addresses during stop-to-move.

Narrowed from snap_spike.py's broader capture. Each candidate is a float
that showed outlier deltas at 5 Hz sampling; this tool polls them at
~5 kHz each to see which ones have a clean one-frame spike at stop-to-move.
"""
import struct, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CANDIDATES = [
    (0x0106E954, "pose +0x384 single"),
    (0x0106E810, "pose +0x240"),
    (0x0106E814, "pose +0x244"),
    (0x0106E910, "pose +0x340"),
    (0x0106E914, "pose +0x344"),
    (0x0106ED54, "pose +0x784"),
    (0x0106E9D4, "pose +0x404"),
    (0x0106A098, "config +0x098"),
    (0x0106CE50, "config +0x2E50"),
    (0x0106E7C0, "rendered forward.x (reference)"),
]

DUR = 3.0

def asf(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]

print(f"[*] Polling {len(CANDIDATES)} candidates for {DUR}s")
print(f"[*] Do ONE decisive stop-to-move push during this window.\n")

results = {a: [] for a, _ in CANDIDATES}
with PineClient() as pc:
    t0 = time.monotonic()
    while time.monotonic() - t0 < DUR:
        for a, _ in CANDIDATES:
            results[a].append(pc.read_u32(a))

print("=== Results ===")
for a, desc in CANDIDATES:
    vals = results[a]
    deltas = [asf(vals[i+1]) - asf(vals[i]) for i in range(len(vals)-1) if vals[i+1] != vals[i]]
    if not deltas:
        print(f"  0x{a:08X}  {desc}: STATIC")
        continue
    abs_deltas = sorted([abs(d) for d in deltas])
    med = abs_deltas[len(abs_deltas)//2]
    mx = abs_deltas[-1]
    ratio = mx / med if med > 0 else 0
    flag = "  <-- SPIKE" if ratio > 10 and mx > 0.0005 else ""
    print(f"  0x{a:08X}  {desc}: changes={len(deltas)}  median={med:.5f}  max={mx:.5f}  ratio={ratio:.1f}x{flag}")

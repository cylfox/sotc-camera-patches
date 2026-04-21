"""Poll multiple candidate float addresses at high rate for 3s, report outliers.

Meant to run while the user performs a decisive stop-to-move push in aim.
Addresses that show a large single-frame delta are likely the ones driving
the visible camera jump.
"""
import struct, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

CANDIDATES = [
    (0x0106D020, "Wander body yaw candidate A"),
    (0x0106D010, "Wander body yaw candidate B"),
    (0x0106C83C, "Wander body yaw candidate C"),
    (0x0106CBC4, "body-facing array[0]"),
    (0x0106CC24, "body-facing array[1]"),
    (0x0106CC84, "body-facing array[2]"),
    (0x0106E7C0, "rendered camera forward.x"),
    (0x0106E7C4, "rendered camera forward.y"),
    (0x0106E7C8, "rendered camera forward.z"),
    (0x01C18610, "basis_a forward.x"),
    (0x01C18614, "basis_a forward.y"),
    (0x01C18618, "basis_a forward.z"),
    (0x0106C230, "direction buffer L1.x"),
    (0x0106C234, "direction buffer L1.y"),
    (0x0106C238, "direction buffer L1.z"),
]

DUR = 3.0

def asf(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]

print(f"[*] Polling {len(CANDIDATES)} candidates for {DUR}s")
print(f"[*] Do a decisive stop-to-move push during this window.\n")

results = {a: [] for a, _ in CANDIDATES}
with PineClient() as pc:
    t0 = time.monotonic()
    while time.monotonic() - t0 < DUR:
        for a, _ in CANDIDATES:
            results[a].append(pc.read_u32(a))

for a, desc in CANDIDATES:
    vals = results[a]
    deltas = [asf(vals[i+1]) - asf(vals[i]) for i in range(len(vals)-1) if vals[i+1] != vals[i]]
    if not deltas:
        print(f"  0x{a:08X}  {desc}: STATIC (never changed)")
        continue
    abs_deltas = sorted([abs(d) for d in deltas])
    med = abs_deltas[len(abs_deltas)//2] if abs_deltas else 0
    mx = abs_deltas[-1] if abs_deltas else 0
    # Flag if max delta > 10× median AND is in a plausible angle range
    if med > 0 and mx / med > 10:
        flag = " <-- OUTLIER"
    else:
        flag = ""
    print(f"  0x{a:08X}  {desc}: changes={len(deltas)}  median={med:.5f}  max={mx:.5f}{flag}")

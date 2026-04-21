"""Capture time-series of camera-related memory during aim stop-to-move.

Polls 3 regions (camera-config, camera-pose, camera-controller) as fast
as PINE allows over 3 seconds. User performs stop-to-move push during
the window. Then for each 4-byte address computes per-sample deltas and
flags addresses whose max delta is >> median delta — those are the
"spike" sources.

Usage: enter aim, hold still. Run script. Push stick once decisively
during the 3s window and release.
"""
import json, os, struct, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

REGIONS = [
    (0x0106A000, 0x4000, "camera config / input state"),
    (0x0106E000, 0x1000, "camera pose"),
    (0x01C18000, 0x2000, "live camera controller"),
]

DUR = 3.0


def capture():
    snapshots = []
    with PineClient() as pc:
        t0 = time.monotonic()
        while time.monotonic() - t0 < DUR:
            snap = {}
            for base, size, _ in REGIONS:
                snap[base] = pc.read_bytes(base, size)
            snapshots.append(snap)
    return snapshots


def analyze(snapshots):
    n = len(snapshots)
    print(f"[*] {n} snapshots over {DUR}s = {n/DUR:.1f} Hz effective rate\n")

    results = []
    for base, size, desc in REGIONS:
        for off in range(0, size, 4):
            addr = base + off
            vals_u32 = [struct.unpack_from('<I', snap[base], off)[0] for snap in snapshots]

            # Skip static
            if all(v == vals_u32[0] for v in vals_u32):
                continue

            vals_f = [struct.unpack('<f', struct.pack('<I', u))[0] for u in vals_u32]

            # Skip if any value is an implausible float (NaN, huge magnitude typical of pointers)
            if any(not (-1e6 < v < 1e6) for v in vals_f):
                continue

            deltas = [abs(vals_f[i+1] - vals_f[i]) for i in range(n-1)]
            nonzero = sorted([d for d in deltas if d > 1e-9])
            if not nonzero:
                continue

            mx = max(deltas)
            med = nonzero[len(nonzero)//2]

            # Keep if there's a meaningful spike
            if med > 0 and mx > med * 8 and mx > 0.0005:
                results.append((addr, mx, med, mx / med))

    # Sort by outlier ratio desc, then by max delta
    results.sort(key=lambda c: (-c[3], -c[1]))
    return results


print("[*] Capturing... perform ONE stop-to-move push during the 3s window.")
snapshots = capture()

cands = analyze(snapshots)
print(f"[*] {len(cands)} addresses with spike signature (max > 8× median, max > 0.0005)\n")

print("=== Top 50 by outlier ratio ===")
for addr, mx, med, ratio in cands[:50]:
    print(f"  0x{addr:08X}  max={mx:.5f}  median={med:.5f}  ratio={ratio:.1f}x")

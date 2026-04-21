"""High-rate poll 0x0106DF00 (camera yaw) for 3s and report sudden deltas.

Meant to run while the user is sweeping the left stick during aim. A
smooth pad-decode integration produces small, roughly-constant per-tick
deltas. A race or double-integration will produce occasional deltas
that are outliers — order of magnitude bigger than the median.
"""
import struct, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

ADDR = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x0106DF00
DUR = 3.0

def as_float(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]

with PineClient() as pc:
    samples = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < DUR:
        samples.append(pc.read_u32(ADDR))

n = len(samples)
deltas = [as_float(samples[i+1]) - as_float(samples[i]) for i in range(n-1) if samples[i+1] != samples[i]]
print(f"samples={n} in {DUR}s  value_changes={len(deltas)}  first={as_float(samples[0]):+.4f}  last={as_float(samples[-1]):+.4f}")

if not deltas:
    print("no changes — register was static")
    sys.exit(0)

abs_deltas = sorted([abs(d) for d in deltas])
med = abs_deltas[len(abs_deltas)//2]
p90 = abs_deltas[int(len(abs_deltas)*0.90)]
p99 = abs_deltas[int(len(abs_deltas)*0.99)] if len(abs_deltas) >= 100 else abs_deltas[-1]
mx = abs_deltas[-1]
print(f"|delta|: median={med:.5f}  p90={p90:.5f}  p99={p99:.5f}  max={mx:.5f}")

# Flag outliers: deltas > 5x median
thresh = max(med * 5, 0.001)
outliers = [(i, d) for i, d in enumerate(deltas) if abs(d) > thresh]
print(f"outlier deltas (|d| > {thresh:.4f}): {len(outliers)} of {len(deltas)}")
for i, d in outliers[:20]:
    print(f"  step {i}: delta={d:+.5f}")

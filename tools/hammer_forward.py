"""Continuously smooth 0x0106E7C0..7C8 (rendered camera forward) via PINE.

Each iteration:
  1. read current forward x/y/z from 0x0106E7C0
  2. lerp the stored copy toward current (alpha = 0.15)
  3. renormalize to unit length (so lerp doesn't shrink the vector)
  4. write the smoothed+normalized vector back to 0x0106E7C0

At >1 kHz iteration rate vs game's 60 Hz update rate, our write dominates
the render-read windows. If the visible stop-to-move jump at 0x0106E7C0
is what the user perceives as "teleport", this should dampen it.

Run in its own terminal; ctrl-C to stop. Doesn't modify any code, only
memory, so safe to abort at any time.
"""
import struct, sys, time, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

FWD_X = 0x0106E7C0
FWD_Y = 0x0106E7C4
FWD_Z = 0x0106E7C8
ALPHA = 0.15

def asf(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]

def asu(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]

print("[*] Hammering 0x0106E7C0..7C8 with smoothed copy (alpha=%.2f). Ctrl-C to stop." % ALPHA)

with PineClient() as pc:
    # Seed with current
    sx = asf(pc.read_u32(FWD_X))
    sy = asf(pc.read_u32(FWD_Y))
    sz = asf(pc.read_u32(FWD_Z))
    print(f"[*] seed forward = ({sx:+.4f}, {sy:+.4f}, {sz:+.4f})")

    t_last = time.monotonic()
    tick = 0
    try:
        while True:
            cx = asf(pc.read_u32(FWD_X))
            cy = asf(pc.read_u32(FWD_Y))
            cz = asf(pc.read_u32(FWD_Z))

            # Lerp toward current
            sx += (cx - sx) * ALPHA
            sy += (cy - sy) * ALPHA
            sz += (cz - sz) * ALPHA

            # Renormalize to preserve unit length
            mag = math.sqrt(sx*sx + sy*sy + sz*sz)
            if mag > 1e-6:
                sx /= mag
                sy /= mag
                sz /= mag

            pc.write_u32(FWD_X, asu(sx))
            pc.write_u32(FWD_Y, asu(sy))
            pc.write_u32(FWD_Z, asu(sz))

            tick += 1
            now = time.monotonic()
            if now - t_last >= 1.0:
                print(f"[*] {tick} iter in {now - t_last:.2f}s = {tick/(now-t_last):.0f} Hz  smoothed=({sx:+.4f},{sy:+.4f},{sz:+.4f}) raw=({cx:+.4f},{cy:+.4f},{cz:+.4f})")
                t_last = now
                tick = 0
    except KeyboardInterrupt:
        print("\n[*] stopped")

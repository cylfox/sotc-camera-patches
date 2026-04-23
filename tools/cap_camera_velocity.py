"""Live-tune the camera yaw AND pitch velocity accumulators.

Background
==========
The game stores per-frame angular-velocity accumulators at
    0x0106DEF8  (yaw vel)    — magnitude + sign of yaw speed, radians
    0x0106DEFC  (yaw delta)  — per-frame yaw delta (≈ yaw_vel / 60)
    0x0106DF04  (pitch vel)  — magnitude + sign of pitch speed, radians
    0x0106DF08  (pitch delta)— per-frame pitch delta (≈ pitch_vel / 60)

Both velocity accumulators ramp UP over ~0.87 s when the stick is held:
    yaw   saturates at 5π/3 ≈ 5.236 (about 300°/s)
    pitch saturates at     ≈ 1.4   (about 80°/s — naturally much tighter)

When the stick is released, each decays back to 0 over another ~0.87 s —
the "coast / drift" after release. Holding → release → hold in the same
direction accumulates compound speed because decay doesn't fully complete
between presses.

This tool hammers each axis at ~125 Hz with three tuning knobs:

  1. CAP          max |velocity| magnitude. Lower = lower max camera
                  speed. Vanilla yaw is ~5.236; pitch is ~1.4.
  2. GROWTH_RATE  fraction of the game's per-frame growth increments
                  we keep. 1.0 = natural, 0.3 = only 30% of each
                  increment lands (70% dampened). Lower = slower ramp.
  3. SNAP_BELOW   once velocity is decaying (magnitude shrinking) AND
                  its value drops below this, we snap it to 0
                  immediately. Higher = camera stops sooner on release.

Presets (user testing, 2026-04-23)
==================================
    v1:  yaw cap=1.5  growth=1.0  snap=0.3         pitch same
         First sweet spot. Natural ramp, light stop.
    v2:  yaw cap=2.0  growth=0.3  snap=1.0         pitch same
         Higher max speed, 70%-dampened ramp, aggressive stop.
    v3:  yaw cap=2.0  growth=0.3  snap=1.5     <-- default
         pitch cap=2.0 growth=0.3  snap=1.0
         Tuned feel: yaw allows a little drift tail, pitch stops
         cleaner since its natural max (1.4) is lower.

Usage
=====
    py cap_camera_velocity.py                     # v3 preset (default)
    py cap_camera_velocity.py --preset v1
    py cap_camera_velocity.py --snap-below 2.0    # v3 but tighter stop
    py cap_camera_velocity.py --cap 2.5 --growth 0.4 --snap-below 1.2
    py cap_camera_velocity.py --off

Override flags apply to BOTH axes. If you want different yaw/pitch
settings, edit the script or start from a preset and tweak via code.

Ctrl+C to stop.

Implementation notes
====================
Hammer rate ≈ 125 Hz (8 ms per iteration); each iteration processes
both yaw and pitch. Growth dampening uses the last value WE wrote as
the reference (not the game's previous write). Decay detection fires
only when the game's fresh write is strictly lower than what we last
wrote, so our own dampening doesn't trigger spurious snaps.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

YAW_VEL_ADDR = 0x0106DEF8
PITCH_VEL_ADDR = 0x0106DF04
HAMMER_INTERVAL = 0.008

# Each preset defines yaw + pitch knobs separately, then overrides can apply
# to both via CLI flags.
PRESETS: dict[str, dict] = {
    "v1": {
        "yaw":   {"cap": 1.5, "growth": 1.0, "snap_below": 0.3},
        "pitch": {"cap": 1.5, "growth": 1.0, "snap_below": 0.3},
    },
    "v2": {
        "yaw":   {"cap": 2.0, "growth": 0.3, "snap_below": 1.0},
        "pitch": {"cap": 2.0, "growth": 0.3, "snap_below": 1.0},
    },
    "v3": {
        "yaw":   {"cap": 2.0, "growth": 0.3, "snap_below": 1.5},
        "pitch": {"cap": 2.0, "growth": 0.3, "snap_below": 1.0},
    },
}


def f32_to_u32(f: float) -> int:
    return struct.unpack('<I', struct.pack('<f', f))[0]


def u32_to_f32(u: int) -> float:
    return struct.unpack('<f', struct.pack('<I', u))[0]


def run(yaw_cfg: dict, pitch_cfg: dict) -> None:
    print(f'[*] YAW   (0x{YAW_VEL_ADDR:08X})   cap={yaw_cfg["cap"]:.2f}  '
          f'growth={yaw_cfg["growth"]:.2f}  snap_below={yaw_cfg["snap_below"]:.2f}')
    print(f'[*] PITCH (0x{PITCH_VEL_ADDR:08X})   cap={pitch_cfg["cap"]:.2f}  '
          f'growth={pitch_cfg["growth"]:.2f}  snap_below={pitch_cfg["snap_below"]:.2f}')
    print('[*] Ctrl+C to stop.')
    print()

    stats = {'yaw': {'cap': 0, 'dampen': 0, 'snap': 0},
             'pitch': {'cap': 0, 'dampen': 0, 'snap': 0}}
    prev_written = {YAW_VEL_ADDR: 0.0, PITCH_VEL_ADDR: 0.0}

    def process_axis(pc: PineClient, addr: int, cfg: dict, tag: str) -> None:
        v = pc.read_u32(addr)
        cur = u32_to_f32(v)
        prev = prev_written[addr]
        abs_cur = abs(cur)
        abs_prev = abs(prev)
        new = cur
        cap = cfg['cap']
        growth = cfg['growth']
        snap = cfg['snap_below']

        # 1. Growth dampening (same-sign growth only)
        if growth < 1.0 and abs_cur > abs_prev and (cur * prev >= 0 or prev == 0):
            new = prev + (cur - prev) * growth
            stats[tag]['dampen'] += 1

        # 2. Cap
        if new > cap:
            new = cap
            stats[tag]['cap'] += 1
        elif new < -cap:
            new = -cap
            stats[tag]['cap'] += 1

        # 3. Snap decay tail
        if snap > 0 and 0 < abs(new) < snap and abs(new) < abs_prev - 1e-4:
            new = 0.0
            stats[tag]['snap'] += 1

        if new != cur:
            pc.write_u32(addr, f32_to_u32(new))
        prev_written[addr] = new

    t_start = time.time()
    try:
        with PineClient() as pc:
            while True:
                process_axis(pc, YAW_VEL_ADDR, yaw_cfg, 'yaw')
                process_axis(pc, PITCH_VEL_ADDR, pitch_cfg, 'pitch')
                time.sleep(HAMMER_INTERVAL)
    except KeyboardInterrupt:
        elapsed = time.time() - t_start
        print()
        print(f'[*] Stopped after {elapsed:.1f}s.')
        for tag in ('yaw', 'pitch'):
            s = stats[tag]
            print(f'    {tag:<5}  caps={s["cap"]:>5}  dampens={s["dampen"]:>5}  snaps={s["snap"]:>5}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--preset', choices=list(PRESETS.keys()),
                    help="Use a named preset (v1, v2, v3). Default v3.")
    ap.add_argument('--cap', type=float, default=None,
                    help="Max |velocity| for BOTH axes. Vanilla yaw ~5.236, pitch ~1.4.")
    ap.add_argument('--growth', type=float, default=None,
                    help="Growth-rate multiplier 0..1 for BOTH axes. 1.0 = natural.")
    ap.add_argument('--snap-below', type=float, default=None,
                    help="Snap to 0 when decaying and |velocity| below this, for BOTH axes.")
    ap.add_argument('--off', action='store_true',
                    help="Don't run; exit immediately.")
    args = ap.parse_args()

    if args.off:
        print('[*] --off: no hammer. Exiting.')
        return

    preset_name = args.preset or 'v3'
    cfg = {
        'yaw': dict(PRESETS[preset_name]['yaw']),
        'pitch': dict(PRESETS[preset_name]['pitch']),
    }
    # CLI overrides apply to both axes
    for axis in ('yaw', 'pitch'):
        if args.cap is not None: cfg[axis]['cap'] = args.cap
        if args.growth is not None: cfg[axis]['growth'] = args.growth
        if args.snap_below is not None: cfg[axis]['snap_below'] = args.snap_below

    print(f'[*] Preset: {preset_name}')
    run(cfg['yaw'], cfg['pitch'])


if __name__ == '__main__':
    main()

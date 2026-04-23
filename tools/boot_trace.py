"""Boot-timing trace: sample pnach target addresses continuously from PCSX2 start
through game boot, to see when the ELF loader writes each address and when
the game becomes 'alive' (game-state flags non-zero).

Run this BEFORE starting PCSX2 (or right after). It will connect via PINE
(may fail initially — will retry), then sample every 100ms for DURATION
seconds, logging every state change.

Run twice:
    1. First without cheats (clean baseline timeline)
    2. Then with cheats (see where the race happens)

Output is a CSV with (timestamp_ms, address, value) for every change.
"""
from __future__ import annotations

import argparse
import csv
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

# Target addresses we care about: pnach writes + game-state flags
TARGETS = [
    # pnach targets (v17_right_aim)
    (0x001ACD44, 'Hook A'),
    (0x001ACD48, 'Hook A delay'),
    (0x001A4984, 'Tramp A+0'),
    (0x001A4988, 'Tramp A+4'),
    (0x001A499C, 'Tramp A last'),
    (0x01176AB4, 'Hook B'),
    (0x001A5248, 'Tramp B+0'),
    (0x001A5274, 'Tramp B last'),
    (0x001003D0, 'Relocation site'),
    # game-state flags (signal boot complete)
    (0x0106C9FC, 'Mode flag'),
    (0x0106B484, 'Aim flag'),
    (0x0106C880, 'Cinematic flag'),
    (0x0106DF00, 'Camera yaw'),
    # A few sentinels in likely-to-change regions
    (0x00100000, 'ELF entry'),
    (0x00200000, 'Mid-code'),
    (0x01000000, 'Globals base'),
]


def wait_for_pine(timeout: float = 60.0) -> PineClient | None:
    """Retry PINE connect until PCSX2 is listening or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        pc = PineClient()
        try:
            pc.connect()
            # Sanity read
            pc.read_u32(0)
            return pc
        except (ConnectionRefusedError, OSError, socket.error):
            pc.close()
            time.sleep(0.5)
    return None


def trace(duration: float, out_path: Path, label: str) -> None:
    print(f'[*] Waiting for PCSX2 PINE (port 28011)...')
    pc = wait_for_pine(timeout=120.0)
    if pc is None:
        print('[!] Timed out. Is PCSX2 running with PINE IPC enabled?')
        return

    print(f'[*] Connected. Sampling for {duration:.0f}s ({label})')
    print(f'[*] Logging to {out_path}')
    print()

    # Initial snapshot
    state = {a: None for a, _ in TARGETS}

    rows: list[tuple[float, int, int, str]] = []
    t0 = time.time()

    print(f'{"t(ms)":>8}  {"addr":>10}  {"value":>10}  {"label"}')
    print('-' * 70)

    try:
        while time.time() - t0 < duration:
            for a, desc in TARGETS:
                try:
                    v = pc.read_u32(a)
                except Exception:
                    continue
                if state[a] != v:
                    elapsed_ms = (time.time() - t0) * 1000
                    rows.append((elapsed_ms, a, v, desc))
                    print(f'{elapsed_ms:>8.0f}  0x{a:08X}  0x{v:08X}  {desc}')
                    state[a] = v
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('\n[*] Stopped.')

    # Save to CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['elapsed_ms', 'addr_hex', 'value_hex', 'label'])
        for ms, a, v, desc in rows:
            w.writerow([f'{ms:.0f}', f'0x{a:08X}', f'0x{v:08X}', desc])

    print()
    print(f'[*] {len(rows)} events captured. Saved to {out_path}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('label', help="tag for this trace (e.g. 'no_cheat' or 'with_cheat')")
    ap.add_argument('--duration', type=float, default=90.0,
                    help='sampling duration in seconds (default 90s)')
    args = ap.parse_args()

    out_dir = Path(__file__).resolve().parent.parent / 'archive' / 'boot_traces'
    out_path = out_dir / f'trace_{args.label}.csv'

    trace(args.duration, out_path, args.label)


if __name__ == '__main__':
    main()

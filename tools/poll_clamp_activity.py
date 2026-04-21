"""Poll v17.1's scratch + mode/aim flags so we can tell whether the aim
path is actually running during the flick test.

Flick the stick in aim mode; the script runs a fixed duration then writes
a summary. Logs include the flag values so we can distinguish "user wasn't
in aim" from "trampoline aim path has a bug".

Usage:
  py tools/poll_clamp_activity.py [duration_seconds]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

SCRATCH_X = 0x001A4A48
SCRATCH_Y = 0x001A4A4C
MODE_FLAG = 0x0106C9FC  # 1 = free-roam, 0 = everything else
AIM_FLAG = 0x0106B484   # 1 = bow-aim, 0 = free-roam/swim/top-of-colossus, 2 = climbing

OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clamp_activity.out")


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    with PineClient() as pc, open(OUT_FILE, "w", encoding="utf-8") as f:
        def log(msg):
            print(msg, flush=True)
            f.write(msg + "\n")
            f.flush()

        log(f"[*] Polling for {duration:.1f}s. Enter aim and flick the stick.")
        prev_x = pc.read_u32(SCRATCH_X) & 0xFF
        prev_y = pc.read_u32(SCRATCH_Y) & 0xFF
        max_step_x = 0
        max_step_y = 0
        samples = 0
        frames_in_aim = 0
        frames_in_freeroam = 0
        start = time.time()
        last_log = start
        while time.time() - start < duration:
            x = pc.read_u32(SCRATCH_X) & 0xFF
            y = pc.read_u32(SCRATCH_Y) & 0xFF
            mode = pc.read_u32(MODE_FLAG)
            aim = pc.read_u32(AIM_FLAG)
            dx = abs(x - prev_x)
            dy = abs(y - prev_y)
            if dx > max_step_x:
                max_step_x = dx
            if dy > max_step_y:
                max_step_y = dy
            if mode == 0 and aim == 1:
                frames_in_aim += 1
            if mode == 1:
                frames_in_freeroam += 1
            samples += 1
            now = time.time()
            if now - last_log >= 1.0:
                log(
                    f"t={now-start:5.1f}s  mode={mode} aim={aim}  "
                    f"prev=(X:0x{x:02X}, Y:0x{y:02X})  "
                    f"cur d=(X:{dx:3}, Y:{dy:3})  "
                    f"max=(X:{max_step_x:3}, Y:{max_step_y:3})"
                )
                last_log = now
            prev_x, prev_y = x, y
            time.sleep(0.016)

        log("")
        log(f"[=] samples={samples}  frames_in_aim={frames_in_aim}  "
            f"frames_in_freeroam={frames_in_freeroam}")
        log(f"[=] Final: max_step_X={max_step_x} (0x{max_step_x:02X})  "
            f"max_step_Y={max_step_y} (0x{max_step_y:02X})")
        if frames_in_aim == 0:
            log("[!] Zero frames observed in aim mode (mode=0, aim=1).")
            log("    Make sure you press the aim button (R1) during the poll.")
        elif max_step_x == 0 and max_step_y == 0:
            log("[!] In aim but scratch never changed. Trampoline aim path is not")
            log("    writing scratch — bug in the patch.")
        elif max_step_x <= 0x22 and max_step_y <= 0x22:
            log("[=] Clamp IS engaging (deltas <= 0x20). Byte rate is not")
            log("    the flicker source — matches investigation's finding that")
            log("    0x0106DF00 is already smooth on reversal.")
        else:
            log("[=] Clamp is NOT engaging (deltas > 0x20).")


if __name__ == "__main__":
    main()

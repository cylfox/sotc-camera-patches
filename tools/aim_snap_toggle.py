"""Python-side aim-snap: Hook B active for ~1s on aim entry, then disabled.

No MIPS changes. Pure PINE. Watches the aim flag in a tight loop and
flips the instruction at the Hook B site between the hook (j to
trampoline) and the original (passthrough swc1) as aim begins/ends.

Behavior:
  aim flag 0 -> 1 (entry):  Hook B enabled, counter starts
  counter expires:           Hook B disabled (aim goes vanilla)
  aim flag 1 -> 0 (exit):    Hook B re-enabled for next entry

Run in a terminal. Ctrl-C to stop — leaves Hook B re-enabled on exit.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK_B_ADDR = 0x01176AB4
HOOK_B_ENABLED  = 0x08069492    # j 0x001A5248
HOOK_B_DISABLED = 0xE7B400B8    # swc1 $f20, 0xb8($sp)  (original)
AIM_FLAG        = 0x0106B484

SNAP_SECONDS = 1.0


def main():
    print(f"[*] aim-snap toggle: Hook B on for first {SNAP_SECONDS}s of aim, then off.")
    print("[*] Ctrl-C to stop.")
    with PineClient() as pc:
        prev_aim = pc.read_u32(AIM_FLAG)
        pc.write_u32(HOOK_B_ADDR, HOOK_B_ENABLED)
        hook_state = "enabled"
        t_snap_end = 0.0
        try:
            while True:
                cur_aim = pc.read_u32(AIM_FLAG)

                # Detect aim entry
                if prev_aim != 1 and cur_aim == 1:
                    pc.write_u32(HOOK_B_ADDR, HOOK_B_ENABLED)
                    hook_state = "enabled"
                    t_snap_end = time.monotonic() + SNAP_SECONDS
                    print(f"[{time.strftime('%H:%M:%S')}] aim entry -> Hook B enabled for {SNAP_SECONDS}s")

                # Timer expired during aim: disable Hook B
                if cur_aim == 1 and hook_state == "enabled" and time.monotonic() >= t_snap_end:
                    pc.write_u32(HOOK_B_ADDR, HOOK_B_DISABLED)
                    hook_state = "disabled"
                    print(f"[{time.strftime('%H:%M:%S')}] snap window ended -> Hook B disabled (vanilla aim)")

                # Aim exit: re-enable Hook B for next entry
                if prev_aim == 1 and cur_aim != 1 and hook_state != "enabled":
                    pc.write_u32(HOOK_B_ADDR, HOOK_B_ENABLED)
                    hook_state = "enabled"
                    print(f"[{time.strftime('%H:%M:%S')}] aim exit -> Hook B re-enabled")

                prev_aim = cur_aim
                time.sleep(0.01)  # 100 Hz polling
        except KeyboardInterrupt:
            # Leave Hook B enabled on exit (safe default)
            pc.write_u32(HOOK_B_ADDR, HOOK_B_ENABLED)
            print("\n[*] stopped; Hook B left enabled")


if __name__ == "__main__":
    main()

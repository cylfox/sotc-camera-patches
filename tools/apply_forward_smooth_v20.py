"""v20: smooth 0x0106C230 right before the VU0 forward-transform consumes it.

Investigation finding: during aim, the yaw/pitch registers 0x0106DF00 /
0x0106DF0C stay smooth, but the direction buffer L1 at 0x0106C230 takes
a ~0.003-magnitude spike on stop-to-move transitions. That spike feeds
into the render-side forward vector at 0x0106E7C0 (via the leaf
function at 0x0125A5C8 which loads [a1] into vf5, runs VU0 macro math,
and stores to [a0+0x1F0]).

v20 hooks the entry of that leaf function, lerps the values at [a1]
against a stored copy with alpha=0.25, writes the smoothed values back
to [a1] (so VU0 loads the smoothed values), then continues the function.

Single-frame spikes become ~4-frame ramps that are invisible.

Hook at 0x0125A5C8:
  0x0125A5C8 <- j 0x00130A98             ; hook (delay slot: moved addiu)
  0x0125A5CC <- addiu a0, a0, 0x01F0     ; original 1st instr moved into delay slot

Trampoline at 0x00130A98 (25 instructions + 4 scratch words):

  +0x00 lwc1 $f0, 0(a1)               ; current[0..2] (direction buffer)
  +0x04 lwc1 $f1, 4(a1)
  +0x08 lwc1 $f2, 8(a1)
  +0x0C lui  t0, 0x0013                ; scratch base 0x00130000
  +0x10 lwc1 $f3, 0x0B00(t0)           ; stored[0..2]
  +0x14 lwc1 $f4, 0x0B04(t0)
  +0x18 lwc1 $f5, 0x0B08(t0)
  +0x1C lwc1 $f6, 0x0B0C(t0)           ; alpha
  +0x20 sub.s $f7, $f0, $f3             ; delta = current - stored
  +0x24 sub.s $f8, $f1, $f4
  +0x28 sub.s $f9, $f2, $f5
  +0x2C mul.s $f7, $f7, $f6             ; delta *= alpha
  +0x30 mul.s $f8, $f8, $f6
  +0x34 mul.s $f9, $f9, $f6
  +0x38 add.s $f3, $f3, $f7             ; stored += delta*alpha (smoothed)
  +0x3C add.s $f4, $f4, $f8
  +0x40 add.s $f5, $f5, $f9
  +0x44 swc1 $f3, 0x0B00(t0)           ; persist stored
  +0x48 swc1 $f4, 0x0B04(t0)
  +0x4C swc1 $f5, 0x0B08(t0)
  +0x50 swc1 $f3, 0(a1)                ; overwrite [a1] with smoothed
  +0x54 swc1 $f4, 4(a1)
  +0x58 swc1 $f5, 8(a1)
  +0x5C j    0x0125A5D0                ; return past the original lqc2
  +0x60 lqc2 vf5, 0(a1)                ; [delay slot] load smoothed into vf5

  +0x68 stored[0] (seeded from [a1] at apply time)
  +0x6C stored[1]
  +0x70 stored[2]
  +0x74 alpha = 0.25 = 0x3E800000
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x0125A5C8
HOOK_DELAY = 0x0125A5CC
HOOK_VAL = 0x0804C2A6          # j 0x00130A98
HOOK_DELAY_VAL = 0x248401F0    # addiu a0, a0, 0x01F0 (moved from 0x0125A5C8)

TRAMP = 0x00130A98

PATCHES = [
    (TRAMP + 0x00, 0xC4A00000, "lwc1 $f0, 0(a1)       ; current[0]"),
    (TRAMP + 0x04, 0xC4A10004, "lwc1 $f1, 4(a1)       ; current[1]"),
    (TRAMP + 0x08, 0xC4A20008, "lwc1 $f2, 8(a1)       ; current[2]"),
    (TRAMP + 0x0C, 0x3C080013, "lui t0, 0x0013        ; scratch base"),
    (TRAMP + 0x10, 0xC5030B00, "lwc1 $f3, 0x0B00(t0)  ; stored[0]"),
    (TRAMP + 0x14, 0xC5040B04, "lwc1 $f4, 0x0B04(t0)  ; stored[1]"),
    (TRAMP + 0x18, 0xC5050B08, "lwc1 $f5, 0x0B08(t0)  ; stored[2]"),
    (TRAMP + 0x1C, 0xC5060B0C, "lwc1 $f6, 0x0B0C(t0)  ; alpha"),
    (TRAMP + 0x20, 0x460301C1, "sub.s $f7, $f0, $f3   ; delta[0]"),
    (TRAMP + 0x24, 0x46040A01, "sub.s $f8, $f1, $f4   ; delta[1]"),
    (TRAMP + 0x28, 0x46051241, "sub.s $f9, $f2, $f5   ; delta[2]"),
    (TRAMP + 0x2C, 0x460639C2, "mul.s $f7, $f7, $f6   ; delta[0] *= alpha"),
    (TRAMP + 0x30, 0x46064202, "mul.s $f8, $f8, $f6"),
    (TRAMP + 0x34, 0x46064A42, "mul.s $f9, $f9, $f6"),
    (TRAMP + 0x38, 0x460718C0, "add.s $f3, $f3, $f7   ; stored[0] += delta"),
    (TRAMP + 0x3C, 0x46082100, "add.s $f4, $f4, $f8"),
    (TRAMP + 0x40, 0x46092940, "add.s $f5, $f5, $f9"),
    (TRAMP + 0x44, 0xE5030B00, "swc1 $f3, 0x0B00(t0)  ; persist"),
    (TRAMP + 0x48, 0xE5040B04, "swc1 $f4, 0x0B04(t0)"),
    (TRAMP + 0x4C, 0xE5050B08, "swc1 $f5, 0x0B08(t0)"),
    (TRAMP + 0x50, 0xE4A30000, "swc1 $f3, 0(a1)       ; [a1] = smoothed"),
    (TRAMP + 0x54, 0xE4A40004, "swc1 $f4, 4(a1)"),
    (TRAMP + 0x58, 0xE4A50008, "swc1 $f5, 8(a1)"),
    (TRAMP + 0x5C, 0x08496974, "j 0x0125A5D0          ; return to VU0 transform"),
    (TRAMP + 0x60, 0xD8A50000, "lqc2 vf5, 0(a1)       ; [delay] re-do load with smoothed val"),
]

SCRATCH_BASE  = 0x00130B00
SCRATCH_ALPHA = 0x00130B0C
ALPHA_F32     = 0x3E800000      # 0.25

DIR_BUFFER = 0x0106C230


def apply():
    with PineClient() as pc:
        print("[*] Applying v20 (smooth 0x0106C230 at leaf transform 0x0125A5C8)")

        # Write trampoline body first
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        # Seed scratch with current direction-buffer values so first invocation
        # doesn't lerp from 0 toward the true value.
        for i in range(3):
            v = pc.read_u32(DIR_BUFFER + i*4)
            pc.write_u32(SCRATCH_BASE + i*4, v)
            print(f"  0x{SCRATCH_BASE + i*4:08X} <- 0x{v:08X}  stored[{i}] seeded")

        pc.write_u32(SCRATCH_ALPHA, ALPHA_F32)
        print(f"  0x{SCRATCH_ALPHA:08X} <- 0x{ALPHA_F32:08X}  alpha = 0.25")

        # Install hook at 0x0125A5C8 + delay slot
        pc.write_u32(HOOK_DELAY, HOOK_DELAY_VAL)   # Write delay slot FIRST
        pc.write_u32(HOOK, HOOK_VAL)                # Then hook (so partial state is safe)
        print(f"  0x{HOOK_DELAY:08X} <- 0x{HOOK_DELAY_VAL:08X}  delay: addiu a0, a0, 0x01F0 (moved)")
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  hook: j 0x{TRAMP:08X}")

        print("[*] Applied. Direction buffer lerp active with alpha=0.25.")
        return True


def restore():
    with PineClient() as pc:
        # Restore hook site
        pc.write_u32(HOOK, 0x248401F0)        # original: addiu a0, a0, 0x01F0
        pc.write_u32(HOOK_DELAY, 0xD8A50000)  # original: lqc2 vf5, 0(a1)
        # Clear trampoline
        for a, _, _ in PATCHES:
            pc.write_u32(a, 0)
        for i in range(4):
            pc.write_u32(SCRATCH_BASE + i*4, 0)
        print("[*] Restored 0x0125A5C8 to original.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()

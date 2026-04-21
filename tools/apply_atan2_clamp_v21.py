"""v21: delta-clamp at the atan2 writer inside the matrix builder.

Hook PC = 0x01176CB8 (the `swc1 f01, 0x0(s2)` that stores the atan2-
derived scalar angle). The theory from the write-BP disassembly:
that instruction is inside a 3D-atan2 helper whose output can have
a sign-flip discontinuity on direction reversal, producing a single-
frame step that propagates through the matrix-builder pipeline to
the rendered forward vector at 0x0106E7C0.

Strategy: before the store, read the previous value at [s2], compute
|delta| = |new - prev|. If |delta| > THRESHOLD (0.1 rad ≈ 5.7°), use
the previous value instead (clamp delta to zero for that frame).
Smooth frame-to-frame motion (< THRESHOLD) passes through unchanged,
only the pathological single-frame jumps on reversal get suppressed.

Hook:
  0x01176CB8 <- j 0x00130A98        ; replaces original swc1 f01, 0(s2)
  0x01176CBC  [unchanged] lqc2 vf05, 0(sp)  ; original, runs in delay slot

Trampoline at 0x00130A98 (12 instructions):

  +0x00 lwc1  $f02, 0x0(s2)          ; f02 = previous stored value
  +0x04 sub.s $f03, $f01, $f02        ; f03 = new - prev
  +0x08 abs.s $f05, $f03               ; f05 = |delta|
  +0x0C lui   t0, 0x0013               ; t0 = 0x00130000
  +0x10 lwc1  $f04, 0x0AD0(t0)        ; f04 = THRESHOLD constant
  +0x14 c.lt.s $f04, $f05              ; cc = (threshold < |delta|)
  +0x18 bc1f  skip_clamp (+2)          ; cc false -> normal, skip clamp
  +0x1C nop                            ; [delay slot]
  +0x20 mov.s $f01, $f02                ; clamp: use previous value
  +0x24 skip_clamp: swc1 $f01, 0x0(s2) ; store (maybe-clamped)
  +0x28 j     0x01176CC0                ; return past original lqc2
  +0x2C nop

  +0x38 threshold = 0.1f = 0x3DCCCCCD
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176CB8
HOOK_VAL = 0x0804C2A6              # j 0x00130A98
HOOK_ORIG = 0xE6410000             # swc1 f01, 0x0(s2)  (original)

TRAMP = 0x00130A98

PATCHES = [
    (TRAMP + 0x00, 0xC6420000, "lwc1 $f02, 0x0(s2)      ; f02 = prev"),
    (TRAMP + 0x04, 0x460208C1, "sub.s $f03, $f01, $f02  ; delta = new - prev"),
    (TRAMP + 0x08, 0x46001945, "abs.s $f05, $f03         ; |delta|"),
    (TRAMP + 0x0C, 0x3C080013, "lui t0, 0x0013           ; scratch base"),
    (TRAMP + 0x10, 0xC5040AD0, "lwc1 $f04, 0x0AD0(t0)   ; threshold"),
    (TRAMP + 0x14, 0x4605203C, "c.lt.s $f04, $f05        ; threshold < |delta|?"),
    (TRAMP + 0x18, 0x45000002, "bc1f +2                  ; normal -> skip clamp"),
    (TRAMP + 0x1C, 0x00000000, "nop                      [branch delay]"),
    (TRAMP + 0x20, 0x46001046, "mov.s $f01, $f02         ; clamp to prev"),
    (TRAMP + 0x24, 0xE6410000, "swc1 $f01, 0x0(s2)      ; store"),
    (TRAMP + 0x28, 0x0845DB30, "j 0x01176CC0             ; return"),
    (TRAMP + 0x2C, 0x00000000, "nop                      [jump delay]"),
]

SCRATCH_THRESHOLD = 0x00130AD0
THRESHOLD_F32 = 0x3DCCCCCD         # 0.1f


def apply():
    with PineClient() as pc:
        print("[*] Applying v21 (atan2 delta-clamp at 0x01176CB8)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        pc.write_u32(SCRATCH_THRESHOLD, THRESHOLD_F32)
        print(f"  0x{SCRATCH_THRESHOLD:08X} <- 0x{THRESHOLD_F32:08X}  threshold = 0.1f")

        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  hook: j 0x{TRAMP:08X}")

        print("[*] Applied. Atan2 writer clamps large single-frame deltas.")
        return True


def restore():
    with PineClient() as pc:
        pc.write_u32(HOOK, HOOK_ORIG)
        for a, _, _ in PATCHES:
            pc.write_u32(a, 0)
        pc.write_u32(SCRATCH_THRESHOLD, 0)
        print("[*] Restored 0x01176CB8 to original swc1.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        apply()

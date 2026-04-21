"""v22 (option B): break matrix-builder feedback loop by resetting [s1].

At Hook B time (entry of matrix builder at 0x01176AA0 + 0x14), $s1
holds the caller's a0 = 0x0106C230 (direction buffer). We extend Hook
B's trampoline to zero-out [s1+0..4] and set [s1+8] = 1.0, so the
buffer becomes reference vector (0, 0, 1, 0) every frame before the
matrix builder's two jal 0x001B3F08 transforms run.

If this works: aim direction is deterministic from $f12/$f13 alone,
with no feedback from the previous frame's output -> no spike
amplification -> direction-reversal jump should disappear.

If it breaks aim: the matrix builder actually uses [s1] as the
previous-frame state for incremental rotation, and forcing a fixed
reference disconnects Wander's body from the camera. Revert.

Trampoline B at 0x001A5248 (v22, 17 instructions):
  +0x00 swc1 $f20, 0xb8($sp)
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)         ; mode flag
  +0x0C bne  at, zero, RET(+12)      ; free-roam -> skip
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)         ; cinematic flag
  +0x18 beq  at, zero, RET(+8)       ; cinematic -> skip
  +0x1C nop
  +0x20 lwc1 $f13, -0x20F4(t0)       ; camera pitch
  +0x24 lwc1 $f12, -0x2100(t0)       ; camera yaw
  +0x28 sw   $zero, 0x0($s1)          ; [v22] [s1+0]  = 0
  +0x2C sw   $zero, 0x4($s1)          ; [v22] [s1+4]  = 0
  +0x30 lui  $t1, 0x3F80               ; [v22] t1 = 1.0f
  +0x34 sw   $t1, 0x8($s1)             ; [v22] [s1+8] = 1.0
  +0x38 sw   $zero, 0xC($s1)           ; [v22] [s1+12] = 0
  +0x3C j    0x01176ABC                ; RET
  +0x40 nop
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_VAL = 0x08069492         # j 0x001A5248

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)       ; mode flag"),
    (TRAMP + 0x0C, 0x1420000C, "bne at, zero, RET(+12)   ; free-roam -> skip"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)       ; cinematic flag"),
    (TRAMP + 0x18, 0x10200008, "beq at, zero, RET(+8)    ; cinematic -> skip"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0xC50DDF0C, "lwc1 $f13, -0x20F4(t0)   ; camera pitch"),
    (TRAMP + 0x24, 0xC50CDF00, "lwc1 $f12, -0x2100(t0)   ; camera yaw"),
    (TRAMP + 0x28, 0xAE200000, "sw $zero, 0x0($s1)        ; [v22] reset x"),
    (TRAMP + 0x2C, 0xAE200004, "sw $zero, 0x4($s1)        ; [v22] reset y"),
    (TRAMP + 0x30, 0x3C093F80, "lui $t1, 0x3F80            ; [v22] 1.0f"),
    (TRAMP + 0x34, 0xAE290008, "sw $t1, 0x8($s1)           ; [v22] z = 1.0"),
    (TRAMP + 0x38, 0xAE20000C, "sw $zero, 0xC($s1)         ; [v22] w = 0"),
    (TRAMP + 0x3C, 0x0845DAAF, "j 0x01176ABC              ; RET"),
    (TRAMP + 0x40, 0x00000000, "nop                       [jump delay]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v22 (option B: break feedback loop)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  Hook B")
        print("[*] Applied. [s1] reset to (0,0,1,0) each frame before matrix transforms.")
        return True


def restore_v16():
    """Go back to v16 Trampoline B (no feedback break)."""
    V16 = [
        (TRAMP + 0x00, 0xE7B400B8),
        (TRAMP + 0x04, 0x3C080107),
        (TRAMP + 0x08, 0x8D01C9FC),
        (TRAMP + 0x0C, 0x14200006),
        (TRAMP + 0x10, 0x00000000),
        (TRAMP + 0x14, 0x8D01C880),
        (TRAMP + 0x18, 0x10200003),
        (TRAMP + 0x1C, 0x00000000),
        (TRAMP + 0x20, 0xC50DDF0C),
        (TRAMP + 0x24, 0xC50CDF00),
        (TRAMP + 0x28, 0x0845DAAF),
        (TRAMP + 0x2C, 0x00000000),
    ]
    with PineClient() as pc:
        for a, v in V16:
            pc.write_u32(a, v)
        # Clear v22 tail
        for off in range(0x30, 0x44, 4):
            pc.write_u32(TRAMP + off, 0)
        pc.write_u32(HOOK, HOOK_VAL)
        print("[*] Reverted to v16 Trampoline B.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_v16()
    else:
        apply()

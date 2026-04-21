"""v16: Trampoline B also overrides aim-pitch ($f13) with camera pitch.

Adds one instruction over v14. $f13 loaded from 0x0106DF0C (camera
pitch register, adjacent to the yaw register at 0x0106DF00). With
this, the aim direction on entry inherits both yaw AND pitch from the
camera — so if you were looking up a hill and press aim, the aim
starts looking up instead of resetting to horizontal (vanilla).

v14 -> v16 changes (three words):
  +0x0C bne  offset  +5 -> +6   (0x14200005 -> 0x14200006)
  +0x18 beq  offset  +2 -> +3   (0x10200002 -> 0x10200003)
  +0x20 NEW:         lwc1 $f13, -0x20F4(t0)   (0xC50DDF0C)
  [everything from the original +0x20 shifts down one word]

Layout at 0x001A5248 (12 instructions):
  +0x00 swc1 $f20, 0xb8($sp)     ; restore clobbered
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)     ; mode flag
  +0x0C bne  at, zero, RET(+6)   ; free-roam -> skip override
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)     ; cinematic flag
  +0x18 beq  at, zero, RET(+3)   ; cinematic -> skip override
  +0x1C nop
  +0x20 lwc1 $f13, -0x20F4(t0)   ; [v16] pitch override: f13 = camera pitch
  +0x24 lwc1 $f12, -0x2100(t0)   ; yaw override: f12 = camera yaw
  +0x28 j    0x01176ABC          ; RET
  +0x2C nop
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_VAL = 0x08069492

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)   ; restore clobbered"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)     ; mode flag 0x0106C9FC"),
    (TRAMP + 0x0C, 0x14200006, "bne at, zero, RET(+6)  ; free-roam -> skip"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)     ; cinematic flag"),
    (TRAMP + 0x18, 0x10200003, "beq at, zero, RET(+3)  ; cinematic -> skip"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0xC50DDF0C, "lwc1 $f13, -0x20F4(t0) ; [v16] camera PITCH -> f13"),
    (TRAMP + 0x24, 0xC50CDF00, "lwc1 $f12, -0x2100(t0) ; camera yaw -> f12"),
    (TRAMP + 0x28, 0x0845DAAF, "j 0x01176ABC           ; RET"),
    (TRAMP + 0x2C, 0x00000000, "nop                    [jump delay]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v16 (Trampoline B also overrides aim pitch)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  Hook B: j 0x001A5248")
        print("[*] Applied. Aim entry now inherits camera pitch in addition to yaw.")
        return True


if __name__ == "__main__":
    apply()

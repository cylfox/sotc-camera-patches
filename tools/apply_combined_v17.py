"""v17: Trampoline A adds a left-Y -> right-Y scratch remap during aim.

Mirrors the existing left-X -> right-X remap. After this change, during
aim mode the aim path writes:
  s0+0x56 <- left-X byte   (camera yaw input; v7 behavior, unchanged)
  s0+0x57 <- left-Y byte   (camera pitch input; NEW in v17)

Downstream the free-roam pad-decode reads s0+0x56 and s0+0x57 into the
camera yaw/pitch registers (0x0106DF00 / 0x0106DF0C). Trampoline B's
v16 override then reads those registers into the aim matrix builder's
$f12/$f13. Net effect during aim:
  - left-X: yaws camera & aim (as before)
  - left-Y: pitches camera & aim (NEW — previously dead)
  - right stick: does nothing visible in aim (its scratch slots are
    overwritten by the left-stick remap)

Implementation detail: the RET path's jump-delay slot is `sb v0, 0x57(s0)`
which would clobber our s0+0x57 write if we wrote it directly. Instead,
we set v0 = left-Y byte (via `lbu v0, 0x109(s2)`) before taking RET, so
the delay-slot store writes our left-Y value into s0+0x57.

Only one instruction added vs v15. All subsequent branch/j targets
shift down by one word.

Layout (21 instructions at 0x001A4984):
  +0x00 lui   at, 0x0107
  +0x04 lw    at, -0x3604(at)        ; mode flag 0x0106C9FC
  +0x08 bne   at, zero, DEADZONE(+11)
  +0x0C nop
  +0x10 lui   at, 0x0107
  +0x14 lw    at, -0x4B7C(at)        ; aim flag 0x0106B484
  +0x18 addiu at, at, -1              ; at = aim - 1
  +0x1C bne   at, zero, DEADZONE(+6)  ; aim != 1 -> deadzone
  +0x20 nop
  +0x24 lbu   t0, 0x108(s2)           ; aim: left-X byte
  +0x28 sb    t0, 0x56(s0)            ; aim: overwrite right-X scratch
  +0x2C lbu   v0, 0x109(s2)           ; [v17] v0 = left-Y byte
  +0x30 j     0x001A49D0              ; -> RET (target shifted from v15)
  +0x34 nop
  +0x38 addiu at, v0, -0x41           ; DEADZONE
  +0x3C sltiu at, at, 0x7F
  +0x40 beq   at, zero, RET(+2)       ; outside -> RET
  +0x44 nop
  +0x48 addiu v0, zero, 0xC0
  +0x4C j     0x001ACD4C              ; RET
  +0x50 sb    v0, 0x57(s0)            ; [delay slot: stores left-Y in aim path]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)          ; mode flag"),
    (TRAMP + 0x08, 0x1420000B, "bne at, zero, DEADZONE(+11) ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x3C010107, "lui at, 0x0107              ; reload"),
    (TRAMP + 0x14, 0x8C21B484, "lw at, -0x4B7C(at)          ; AIM flag 0x0106B484"),
    (TRAMP + 0x18, 0x2421FFFF, "addiu at, at, -1            ; at = aim - 1"),
    (TRAMP + 0x1C, 0x14200006, "bne at, zero, DEADZONE(+6)  ; aim != 1 -> deadzone"),
    (TRAMP + 0x20, 0x00000000, "nop"),
    (TRAMP + 0x24, 0x92480108, "lbu t0, 0x108(s2)           ; aim: left-X byte"),
    (TRAMP + 0x28, 0xA2080056, "sb  t0, 0x56(s0)            ; aim: remap X"),
    (TRAMP + 0x2C, 0x92420109, "lbu v0, 0x109(s2)           ; [v17] v0 = left-Y byte"),
    (TRAMP + 0x30, 0x08069274, "j 0x001A49D0                ; -> RET"),
    (TRAMP + 0x34, 0x00000000, "nop"),
    (TRAMP + 0x38, 0x2441FFBF, "DEADZONE: addiu at, v0, -0x41"),
    (TRAMP + 0x3C, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0x40, 0x10200002, "beq at, zero, RET(+2)       ; outside deadzone -> ret"),
    (TRAMP + 0x44, 0x00000000, "nop"),
    (TRAMP + 0x48, 0x240200C0, "addiu v0, zero, 0xC0        ; substitute"),
    (TRAMP + 0x4C, 0x0806B353, "RET: j 0x001ACD4C"),
    (TRAMP + 0x50, 0xA2020057, "sb v0, 0x57(s0)             [delay slot]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v17 (aim: left-Y also remapped -> right-Y scratch)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        print("[*] Applied. Aim now takes both axes from left stick.")
        return True


if __name__ == "__main__":
    apply()

"""v17.2: v17.1 + stack-spill of clobbered caller-saved registers.

v17.1 broke aim-mode control (pitch stuck, couldn't exit aim) because
the pad-decode caller has at least one of t1/t2/t3/t9 live across the
hook; clobbering those crashed the caller's input state. v16/v17 got
away with clobbering t0 only because t0 is dead at the hook site.

Fix: on aim-path entry, push t1, t2, t3, t9 to the stack; pop them
before returning via RET. DEADZONE path is untouched — it only uses
`at` (which is reserved and always caller-clobberable) and `v0`
(which the hook's delay slot already wrote).

Also moved scratch from 0x001A4A48/4C (inside the v17.1 extended
trampoline footprint — potentially overlapping padding the game
writes to) to 0x001A4A70/74, cleanly past the v17.2 body end at
0x001A4A68.

Trampoline A v17.2 layout (58 instructions + 2 scratch words):

  +0x00 lui   at, 0x0107
  +0x04 lw    at, -0x3604(at)         ; mode flag
  +0x08 bne   at, zero, DEADZONE(+48)
  +0x0C nop
  +0x10 lui   at, 0x0107
  +0x14 lw    at, -0x4B7C(at)         ; AIM flag
  +0x18 addiu at, at, -1
  +0x1C bne   at, zero, DEADZONE(+43)
  +0x20 nop
  ; --- aim path: stack-spill t1/t2/t3/t9 ---
  +0x24 addiu sp, sp, -16
  +0x28 sw    t1, 0(sp)
  +0x2C sw    t2, 4(sp)
  +0x30 sw    t3, 8(sp)
  +0x34 sw    t9, 12(sp)
  ; --- left-X delta clamp ---
  +0x38 lbu   t0, 0x108(s2)           ; new left-X
  +0x3C lui   t9, 0x001A               ; scratch base
  +0x40 lbu   t1, 0x4A70(t9)          ; prev left-X
  +0x44 subu  t2, t0, t1              ; delta
  +0x48 slti  t3, t2, 0x21            ; delta < 33?
  +0x4C bnez  t3, chk_neg_X(+4)
  +0x50 nop
  +0x54 addiu t0, t1, 0x20            ; clamp high: prev + 32
  +0x58 b     store_X(+5)
  +0x5C nop
  +0x60 addiu t3, t2, 0x20             ; chk_neg_X: delta + 32
  +0x64 bgez  t3, store_X(+2)
  +0x68 nop
  +0x6C addiu t0, t1, -0x20            ; clamp low: prev - 32
  +0x70 sb    t0, 0x56(s0)             ; store_X: right-X scratch
  +0x74 sb    t0, 0x4A70(t9)           ; persist prev_X
  ; --- left-Y delta clamp ---
  +0x78 lbu   v0, 0x109(s2)            ; new left-Y
  +0x7C lbu   t1, 0x4A74(t9)           ; prev left-Y
  +0x80 subu  t2, v0, t1
  +0x84 slti  t3, t2, 0x21
  +0x88 bnez  t3, chk_neg_Y(+4)
  +0x8C nop
  +0x90 addiu v0, t1, 0x20              ; clamp high
  +0x94 b     store_Y(+5)
  +0x98 nop
  +0x9C addiu t3, t2, 0x20              ; chk_neg_Y
  +0xA0 bgez  t3, store_Y(+2)
  +0xA4 nop
  +0xA8 addiu v0, t1, -0x20             ; clamp low
  +0xAC sb    v0, 0x4A74(t9)            ; store_Y: persist prev_Y
  ; --- aim path: restore ---
  +0xB0 lw    t1, 0(sp)
  +0xB4 lw    t2, 4(sp)
  +0xB8 lw    t3, 8(sp)
  +0xBC lw    t9, 12(sp)
  +0xC0 addiu sp, sp, 16
  +0xC4 j     RET (0x001A4A64)          ; v0 = clamped left-Y
  +0xC8 nop
  ; --- DEADZONE (unchanged semantics, relocated) ---
  +0xCC addiu at, v0, -0x41
  +0xD0 sltiu at, at, 0x7F
  +0xD4 beq   at, zero, RET(+2)
  +0xD8 nop
  +0xDC addiu v0, zero, 0xC0
  ; --- RET ---
  +0xE0 j     0x001ACD4C
  +0xE4 sb    v0, 0x57(s0)              ; [delay slot]
  ; --- scratch ---
  +0xEC  prev_X (0x001A4A70, seeded 0x80)
  +0xF0  prev_Y (0x001A4A74, seeded 0x80)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984
SCRATCH_PREV_X = 0x001A4A70
SCRATCH_PREV_Y = 0x001A4A74

PATCHES = [
    # --- gating ---
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)           ; mode flag"),
    (TRAMP + 0x08, 0x14200030, "bne at, zero, DEADZONE (+48) ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x14, 0x8C21B484, "lw at, -0x4B7C(at)           ; AIM flag"),
    (TRAMP + 0x18, 0x2421FFFF, "addiu at, at, -1"),
    (TRAMP + 0x1C, 0x1420002B, "bne at, zero, DEADZONE (+43) ; aim != 1 -> deadzone"),
    (TRAMP + 0x20, 0x00000000, "nop"),

    # --- aim path: save clobbered caller regs ---
    (TRAMP + 0x24, 0x27BDFFF0, "addiu sp, sp, -16"),
    (TRAMP + 0x28, 0xAFA90000, "sw t1, 0(sp)"),
    (TRAMP + 0x2C, 0xAFAA0004, "sw t2, 4(sp)"),
    (TRAMP + 0x30, 0xAFAB0008, "sw t3, 8(sp)"),
    (TRAMP + 0x34, 0xAFB9000C, "sw t9, 12(sp)"),

    # --- left-X delta clamp ---
    (TRAMP + 0x38, 0x92480108, "lbu t0, 0x108(s2)            ; new left-X"),
    (TRAMP + 0x3C, 0x3C19001A, "lui t9, 0x001A               ; scratch base"),
    (TRAMP + 0x40, 0x93294A70, "lbu t1, 0x4A70(t9)           ; prev left-X"),
    (TRAMP + 0x44, 0x01095023, "subu t2, t0, t1              ; delta"),
    (TRAMP + 0x48, 0x294B0021, "slti t3, t2, 0x21"),
    (TRAMP + 0x4C, 0x15600004, "bnez t3, chk_neg_X (+4)"),
    (TRAMP + 0x50, 0x00000000, "nop"),
    (TRAMP + 0x54, 0x25280020, "addiu t0, t1, 0x20           ; clamp high"),
    (TRAMP + 0x58, 0x10000005, "b store_X (+5)"),
    (TRAMP + 0x5C, 0x00000000, "nop"),
    (TRAMP + 0x60, 0x254B0020, "chk_neg_X: addiu t3, t2, 0x20"),
    (TRAMP + 0x64, 0x05610002, "bgez t3, store_X (+2)"),
    (TRAMP + 0x68, 0x00000000, "nop"),
    (TRAMP + 0x6C, 0x2528FFE0, "addiu t0, t1, -0x20          ; clamp low"),
    (TRAMP + 0x70, 0xA2080056, "store_X: sb t0, 0x56(s0)"),
    (TRAMP + 0x74, 0xA3284A70, "sb t0, 0x4A70(t9)            ; persist prev_X"),

    # --- left-Y delta clamp ---
    (TRAMP + 0x78, 0x92420109, "lbu v0, 0x109(s2)            ; new left-Y"),
    (TRAMP + 0x7C, 0x93294A74, "lbu t1, 0x4A74(t9)           ; prev left-Y"),
    (TRAMP + 0x80, 0x004A5023, "subu t2, v0, t1"),
    (TRAMP + 0x84, 0x294B0021, "slti t3, t2, 0x21"),
    (TRAMP + 0x88, 0x15600004, "bnez t3, chk_neg_Y (+4)"),
    (TRAMP + 0x8C, 0x00000000, "nop"),
    (TRAMP + 0x90, 0x25220020, "addiu v0, t1, 0x20           ; clamp high"),
    (TRAMP + 0x94, 0x10000005, "b store_Y (+5)"),
    (TRAMP + 0x98, 0x00000000, "nop"),
    (TRAMP + 0x9C, 0x254B0020, "chk_neg_Y: addiu t3, t2, 0x20"),
    (TRAMP + 0xA0, 0x05610002, "bgez t3, store_Y (+2)"),
    (TRAMP + 0xA4, 0x00000000, "nop"),
    (TRAMP + 0xA8, 0x2522FFE0, "addiu v0, t1, -0x20          ; clamp low"),
    (TRAMP + 0xAC, 0xA3224A74, "store_Y: sb v0, 0x4A74(t9)   ; persist prev_Y"),

    # --- aim path: restore ---
    (TRAMP + 0xB0, 0x8FA90000, "lw t1, 0(sp)"),
    (TRAMP + 0xB4, 0x8FAA0004, "lw t2, 4(sp)"),
    (TRAMP + 0xB8, 0x8FAB0008, "lw t3, 8(sp)"),
    (TRAMP + 0xBC, 0x8FB9000C, "lw t9, 12(sp)"),
    (TRAMP + 0xC0, 0x27BD0010, "addiu sp, sp, 16"),
    (TRAMP + 0xC4, 0x08069599, "j 0x001A4A64 (RET)"),
    (TRAMP + 0xC8, 0x00000000, "nop"),

    # --- DEADZONE ---
    (TRAMP + 0xCC, 0x2441FFBF, "DEADZONE: addiu at, v0, -0x41"),
    (TRAMP + 0xD0, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0xD4, 0x10200002, "beq at, zero, RET (+2)"),
    (TRAMP + 0xD8, 0x00000000, "nop"),
    (TRAMP + 0xDC, 0x240200C0, "addiu v0, zero, 0xC0"),

    # --- RET ---
    (TRAMP + 0xE0, 0x0806B353, "RET: j 0x001ACD4C"),
    (TRAMP + 0xE4, 0xA2020057, "sb v0, 0x57(s0)              ; [delay slot]"),
]

SCRATCH_INIT = [
    (SCRATCH_PREV_X, 0x00000080, "prev_X seed = 0x80"),
    (SCRATCH_PREV_Y, 0x00000080, "prev_Y seed = 0x80"),
]

HOOK_A = [
    (0x001ACD44, 0x08069261, "hook A: j 0x001A4984"),
    (0x001ACD48, 0x92420107, "hook A delay slot: lbu v0, 0x107(s2)"),
]
HOOK_B = [
    (0x01176AB4, 0x08069492, "hook B: j 0x001A5248"),
]
TRAMP_B = [
    (0x001A5248, 0xE7B400B8, "swc1 $f20, 0xB8($sp)"),
    (0x001A524C, 0x3C080107, "lui t0, 0x0107"),
    (0x001A5250, 0x8D01C9FC, "lw at, -0x3604(t0)"),
    (0x001A5254, 0x14200006, "bne at, zero, RET(+6)"),
    (0x001A5258, 0x00000000, "nop"),
    (0x001A525C, 0x8D01C880, "lw at, -0x3780(t0)"),
    (0x001A5260, 0x10200003, "beq at, zero, RET(+3)"),
    (0x001A5264, 0x00000000, "nop"),
    (0x001A5268, 0xC50DDF0C, "lwc1 $f13, -0x20F4(t0)"),
    (0x001A526C, 0xC50CDF00, "lwc1 $f12, -0x2100(t0)"),
    (0x001A5270, 0x0845DAAF, "j 0x01176ABC"),
    (0x001A5274, 0x00000000, "nop"),
]


def _write_list(pc, label, items):
    print(f"[*] {label}")
    for addr, val, desc in items:
        pc.write_u32(addr, val)
        got = pc.read_u32(addr)
        ok = "OK" if got == val else "FAIL"
        print(f"  0x{addr:08X} <- 0x{val:08X}  [{ok}]  {desc}")
        if got != val:
            return False
    return True


def apply():
    with PineClient() as pc:
        print("[*] Applying v17.2 (rate-limit + stack-spill of t1/t2/t3/t9)")
        if not _write_list(pc, "Trampoline A body (58 words):", PATCHES):
            return False
        if not _write_list(pc, "Scratch init:", SCRATCH_INIT):
            return False
        if not _write_list(pc, "Hook A (re-assert):", HOOK_A):
            return False
        if not _write_list(pc, "Hook B (re-assert):", HOOK_B):
            return False
        if not _write_list(pc, "Trampoline B (re-assert):", TRAMP_B):
            return False
        print("[*] v17.2 applied. Test aim entry, pitch both ways, and aim-exit.")
        return True


if __name__ == "__main__":
    ok = apply()
    sys.exit(0 if ok else 1)

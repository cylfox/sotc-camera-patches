"""v17.1: per-frame byte-delta rate limiter on the aim-path left-stick remap.

Extends v17's Trampoline A with a two-axis clamp. For each of left-X and
left-Y, reads the previous-frame byte from scratch memory, computes the
signed delta vs. the new pad byte, and if |delta| > CLAMP (= 0x20)
overwrites the byte with prev ± CLAMP before writing it to the right-
stick scratch slot s0+0x56 / s0+0x57.

Everything else is identical to v17:
  - Hook A at 0x001ACD44 still points to 0x001A4984.
  - Hook B at 0x01176AB4 still points to Trampoline B at 0x001A5248.
  - Trampoline B is byte-identical (reads 0x0106DF00 / 0x0106DF0C into
    $f12 / $f13 outside free-roam / cinematic).
  - Free-roam autofocus deadzone substitute unchanged.

Trampoline A grows from 21 -> 48 instructions (0xC0 bytes). Scratch at
0x001A4A48 (prev_X) / 0x001A4A4C (prev_Y) seeded to 0x80 (stick center).

See patch/0F0C4A9C_camera_fix_v17_1_rate_limit.pnach for the full commented
layout. All branch/jump offsets verified.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984
SCRATCH_PREV_X = 0x001A4A48
SCRATCH_PREV_Y = 0x001A4A4C

PATCHES = [
    # --- gating (unchanged semantics; branch offsets shifted for new layout) ---
    (TRAMP + 0x00, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x04, 0x8C21C9FC, "lw at, -0x3604(at)            ; mode flag 0x0106C9FC"),
    (TRAMP + 0x08, 0x14200026, "bne at, zero, DEADZONE (+38)  ; free-roam -> deadzone"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x3C010107, "lui at, 0x0107"),
    (TRAMP + 0x14, 0x8C21B484, "lw at, -0x4B7C(at)            ; AIM flag 0x0106B484"),
    (TRAMP + 0x18, 0x2421FFFF, "addiu at, at, -1"),
    (TRAMP + 0x1C, 0x14200021, "bne at, zero, DEADZONE (+33)  ; aim != 1 -> deadzone"),
    (TRAMP + 0x20, 0x00000000, "nop"),

    # --- aim path: left-X delta clamp ---
    (TRAMP + 0x24, 0x92480108, "lbu t0, 0x108(s2)             ; t0 = new left-X"),
    (TRAMP + 0x28, 0x3C19001A, "lui t9, 0x001A                ; scratch base"),
    (TRAMP + 0x2C, 0x93294A48, "lbu t1, 0x4A48(t9)            ; t1 = prev left-X"),
    (TRAMP + 0x30, 0x01095023, "subu t2, t0, t1               ; delta"),
    (TRAMP + 0x34, 0x294B0021, "slti t3, t2, 0x21             ; (delta < 33)?"),
    (TRAMP + 0x38, 0x15600004, "bnez t3, chk_neg_X (+4)       ; in-range or neg -> check"),
    (TRAMP + 0x3C, 0x00000000, "nop"),
    (TRAMP + 0x40, 0x25280020, "addiu t0, t1, 0x20            ; clamp high: prev + 32"),
    (TRAMP + 0x44, 0x10000005, "b store_X (+5)"),
    (TRAMP + 0x48, 0x00000000, "nop"),
    (TRAMP + 0x4C, 0x254B0020, "chk_neg_X: addiu t3, t2, 0x20 ; t3 = delta + 32"),
    (TRAMP + 0x50, 0x05610002, "bgez t3, store_X (+2)         ; delta >= -32 -> no clamp"),
    (TRAMP + 0x54, 0x00000000, "nop"),
    (TRAMP + 0x58, 0x2528FFE0, "addiu t0, t1, -0x20           ; clamp low: prev - 32"),
    (TRAMP + 0x5C, 0xA2080056, "store_X: sb t0, 0x56(s0)      ; write clamped right-X"),
    (TRAMP + 0x60, 0xA3284A48, "sb t0, 0x4A48(t9)             ; persist prev_X"),

    # --- aim path: left-Y delta clamp ---
    (TRAMP + 0x64, 0x92420109, "lbu v0, 0x109(s2)             ; v0 = new left-Y"),
    (TRAMP + 0x68, 0x93294A4C, "lbu t1, 0x4A4C(t9)            ; t1 = prev left-Y"),
    (TRAMP + 0x6C, 0x004A5023, "subu t2, v0, t1"),
    (TRAMP + 0x70, 0x294B0021, "slti t3, t2, 0x21"),
    (TRAMP + 0x74, 0x15600004, "bnez t3, chk_neg_Y (+4)"),
    (TRAMP + 0x78, 0x00000000, "nop"),
    (TRAMP + 0x7C, 0x25220020, "addiu v0, t1, 0x20            ; clamp high"),
    (TRAMP + 0x80, 0x10000005, "b store_Y (+5)"),
    (TRAMP + 0x84, 0x00000000, "nop"),
    (TRAMP + 0x88, 0x254B0020, "chk_neg_Y: addiu t3, t2, 0x20"),
    (TRAMP + 0x8C, 0x05610002, "bgez t3, store_Y (+2)"),
    (TRAMP + 0x90, 0x00000000, "nop"),
    (TRAMP + 0x94, 0x2522FFE0, "addiu v0, t1, -0x20           ; clamp low"),
    (TRAMP + 0x98, 0xA3224A4C, "store_Y: sb v0, 0x4A4C(t9)    ; persist prev_Y"),
    (TRAMP + 0x9C, 0x0806928F, "j 0x001A4A3C (RET)            ; v0 = clamped left-Y"),
    (TRAMP + 0xA0, 0x00000000, "nop"),

    # --- DEADZONE (same as v17, relocated) ---
    (TRAMP + 0xA4, 0x2441FFBF, "DEADZONE: addiu at, v0, -0x41"),
    (TRAMP + 0xA8, 0x2C21007F, "sltiu at, at, 0x7F"),
    (TRAMP + 0xAC, 0x10200002, "beq at, zero, RET (+2)        ; outside -> RET"),
    (TRAMP + 0xB0, 0x00000000, "nop"),
    (TRAMP + 0xB4, 0x240200C0, "addiu v0, zero, 0xC0          ; substitute"),

    # --- RET ---
    (TRAMP + 0xB8, 0x0806B353, "RET: j 0x001ACD4C"),
    (TRAMP + 0xBC, 0xA2020057, "sb v0, 0x57(s0)               ; [delay slot]"),
]

SCRATCH_INIT = [
    (SCRATCH_PREV_X, 0x00000080, "prev_X seed = 0x80 (stick center)"),
    (SCRATCH_PREV_Y, 0x00000080, "prev_Y seed = 0x80 (stick center)"),
]

# Hook A and Trampoline B are unchanged from v17 — assume pnach already in place.
# Re-assert them for robustness when applying over a cold state.
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
    (0x001A5250, 0x8D01C9FC, "lw at, -0x3604(t0)            ; mode flag"),
    (0x001A5254, 0x14200006, "bne at, zero, RET(+6)"),
    (0x001A5258, 0x00000000, "nop"),
    (0x001A525C, 0x8D01C880, "lw at, -0x3780(t0)            ; cinematic flag"),
    (0x001A5260, 0x10200003, "beq at, zero, RET(+3)"),
    (0x001A5264, 0x00000000, "nop"),
    (0x001A5268, 0xC50DDF0C, "lwc1 $f13, -0x20F4(t0)        ; camera pitch"),
    (0x001A526C, 0xC50CDF00, "lwc1 $f12, -0x2100(t0)        ; camera yaw"),
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
        print("[*] Applying v17.1 (aim-path left-stick byte-delta rate limiter)")
        # Write the extended trampoline body first. Since Hook A already jumps
        # here, this clobbers the live v17 code. The risk window is small
        # (PINE writes are << 1 frame) and consistent with prior apply
        # scripts (v17 clobbers v16 the same way).
        if not _write_list(pc, "Trampoline A body (48 words):", PATCHES):
            return False
        if not _write_list(pc, "Scratch init (prev_X / prev_Y = 0x80):", SCRATCH_INIT):
            return False
        if not _write_list(pc, "Hook A (re-assert):", HOOK_A):
            return False
        if not _write_list(pc, "Hook B (re-assert):", HOOK_B):
            return False
        if not _write_list(pc, "Trampoline B (re-assert, identical to v17):", TRAMP_B):
            return False
        print("[*] v17.1 applied. Test: aim + fast opposite-direction stick flick.")
        print("    Tune CLAMP_MAX by editing the 0x20 / 0xFFE0 / 0x21 literals")
        print("    in the PATCHES list (lower = smoother, higher = snappier).")
        return True


if __name__ == "__main__":
    ok = apply()
    sys.exit(0 if ok else 1)

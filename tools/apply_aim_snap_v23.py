"""v23: Hook B override only fires for the first SNAP_FRAMES of aim entry.

Theory: the stop-to-move flicker only exists because Hook B keeps
rewriting $f12/$f13 every frame during sustained aim. If we let Hook B
do its FPS-snap work for the first ~1 second of aim (enough for
Wander to turn to face the camera direction), then stop overriding,
the subsequent aim flow runs vanilla-style and the flicker vanishes.

Logic per Hook B fire:
  mode_flag != 0: skip (free-roam)
  cinematic_flag == 0: skip (cutscene)
  aim_flag != 1: RESET counter + override (swim / on-colossus / climb — always snap)
  aim_flag == 1:
    if counter > 0: decrement + override
    else: skip override (vanilla aim)

The counter resets every frame outside bow-aim, so each new aim entry
gets its full SNAP_FRAMES window. During actual bow-aim, the window
counts down once and stays at 0 until aim is released.

Trampoline B at 0x001A5248 (27 instructions + 1 scratch word):
  +0x00 swc1 $f20, 0xb8($sp)       ; restore clobbered
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)       ; mode flag 0x0106C9FC
  +0x0C bne  at, zero, RET(+21)    ; free-roam -> skip
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)       ; cinematic flag 0x0106C880
  +0x18 beq  at, zero, RET(+18)    ; cinematic -> skip
  +0x1C nop
  +0x20 lw   at, -0x4B7C(t0)       ; aim flag 0x0106B484
  +0x24 addiu at, at, -1            ; at = aim - 1
  +0x28 bne  at, zero, NOT_BOW_AIM(+9) ; at != 0 -> not bow-aim
  +0x2C nop
  ; --- bow-aim path: check counter ---
  +0x30 lui  t1, 0x001A
  +0x34 lw   t2, 0x52B4(t1)        ; counter
  +0x38 beq  t2, zero, RET(+10)    ; counter expired -> skip override
  +0x3C nop
  +0x40 addiu t2, t2, -1
  +0x44 sw   t2, 0x52B4(t1)        ; save decremented counter
  +0x48 j    0x001A52A4             ; -> OVERRIDE
  +0x4C nop
  ; --- non-bow-aim path: reset counter, fall through to override ---
  +0x50 lui  t1, 0x001A
  +0x54 addiu t2, zero, 60          ; SNAP_FRAMES = 60 (~1s at 60fps)
  +0x58 sw   t2, 0x52B4(t1)
  ; --- override: $f12/$f13 from camera registers ---
  +0x5C lwc1 $f13, -0x20F4(t0)     ; OVERRIDE: camera pitch -> $f13
  +0x60 lwc1 $f12, -0x2100(t0)     ;           camera yaw   -> $f12
  +0x64 j    0x01176ABC             ; RET
  +0x68 nop

Scratch: counter at 0x001A52B4 (32-bit signed int, seeded to 60).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_VAL = 0x08069492

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)       ; mode flag"),
    (TRAMP + 0x0C, 0x14200015, "bne at, zero, RET(+21)   ; free-roam -> skip"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)       ; cinematic flag"),
    (TRAMP + 0x18, 0x10200012, "beq at, zero, RET(+18)   ; cinematic -> skip"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0x8D01B484, "lw at, -0x4B7C(t0)       ; aim flag"),
    (TRAMP + 0x24, 0x2421FFFF, "addiu at, at, -1"),
    (TRAMP + 0x28, 0x14200009, "bne at, zero, NOT_BOW(+9) ; not bow-aim"),
    (TRAMP + 0x2C, 0x00000000, "nop"),
    (TRAMP + 0x30, 0x3C09001A, "lui t1, 0x001A           ; bow-aim: check counter"),
    (TRAMP + 0x34, 0x8D2A52B4, "lw t2, 0x52B4(t1)        ; counter"),
    (TRAMP + 0x38, 0x1140000A, "beq t2, zero, RET(+10)   ; counter expired -> skip"),
    (TRAMP + 0x3C, 0x00000000, "nop"),
    (TRAMP + 0x40, 0x254AFFFF, "addiu t2, t2, -1"),
    (TRAMP + 0x44, 0xAD2A52B4, "sw t2, 0x52B4(t1)"),
    (TRAMP + 0x48, 0x08068CA9, "j 0x001A52A4 (OVERRIDE)"),
    (TRAMP + 0x4C, 0x00000000, "nop"),
    (TRAMP + 0x50, 0x3C09001A, "lui t1, 0x001A           ; non-bow-aim: reset counter"),
    (TRAMP + 0x54, 0x240A003C, "addiu t2, zero, 60       ; SNAP_FRAMES"),
    (TRAMP + 0x58, 0xAD2A52B4, "sw t2, 0x52B4(t1)"),
    (TRAMP + 0x5C, 0xC50DDF0C, "lwc1 $f13, -0x20F4(t0)   ; OVERRIDE: camera pitch"),
    (TRAMP + 0x60, 0xC50CDF00, "lwc1 $f12, -0x2100(t0)   ;           camera yaw"),
    (TRAMP + 0x64, 0x0845DAAF, "j 0x01176ABC             ; RET"),
    (TRAMP + 0x68, 0x00000000, "nop"),
]

SCRATCH_COUNTER = 0x001A52B4
SNAP_FRAMES = 60


def apply():
    with PineClient() as pc:
        print("[*] Applying v23 (aim-snap counter, SNAP_FRAMES=60 ~1s)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        pc.write_u32(SCRATCH_COUNTER, SNAP_FRAMES)
        print(f"  0x{SCRATCH_COUNTER:08X} <- {SNAP_FRAMES}  counter seeded")
        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  Hook B")
        print(f"[*] Applied. Override fires for first {SNAP_FRAMES} frames of aim only.")
        return True


def restore_v16():
    V16 = [
        (TRAMP + 0x00, 0xE7B400B8), (TRAMP + 0x04, 0x3C080107),
        (TRAMP + 0x08, 0x8D01C9FC), (TRAMP + 0x0C, 0x14200006),
        (TRAMP + 0x10, 0x00000000), (TRAMP + 0x14, 0x8D01C880),
        (TRAMP + 0x18, 0x10200003), (TRAMP + 0x1C, 0x00000000),
        (TRAMP + 0x20, 0xC50DDF0C), (TRAMP + 0x24, 0xC50CDF00),
        (TRAMP + 0x28, 0x0845DAAF), (TRAMP + 0x2C, 0x00000000),
    ]
    with PineClient() as pc:
        for a, v in V16:
            pc.write_u32(a, v)
        for off in range(0x30, 0x70, 4):
            pc.write_u32(TRAMP + off, 0)
        pc.write_u32(HOOK, HOOK_VAL)
        print("[*] Reverted to v16 Trampoline B.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_v16()
    else:
        apply()

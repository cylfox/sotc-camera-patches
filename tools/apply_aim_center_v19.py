"""v19: v18 lerp + write smoothed values back to camera registers.

v18 smoothed the aim-matrix $f12/$f13 but the user still saw flicker on
stop-to-move. That suggests the camera view is rendered from the camera
registers 0x0106DF00 / 0x0106DF0C directly, not via $f12 alone. v19
writes the smoothed stored_yaw / stored_pitch BACK to those registers so
the camera-render pipeline also sees the smoothed values.

Two new swc1 instructions added to v18. Scratch addresses shift by one
word because the code grew. All branch/jump targets recomputed.

Layout (28 code instructions + 3 data words at 0x001A5248):

  +0x00 swc1 $f20, 0xb8($sp)        ; restore clobbered
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)        ; mode flag
  +0x0C bne  at, zero, RET(+22)     ; free-roam -> skip
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)        ; cinematic flag
  +0x18 beq  at, zero, RET(+19)     ; cinematic -> skip
  +0x1C nop
  +0x20 lui  t1, 0x001A             ; scratch base
  +0x24 lwc1 $f4, 0x52B8(t1)        ; stored_yaw
  +0x28 lwc1 $f5, 0x52BC(t1)        ; stored_pitch
  +0x2C lwc1 $f6, -0x2100(t0)       ; target_yaw
  +0x30 lwc1 $f7, -0x20F4(t0)       ; target_pitch
  +0x34 sub.s $f6, $f6, $f4          ; delta_yaw
  +0x38 sub.s $f7, $f7, $f5          ; delta_pitch
  +0x3C lwc1 $f8, 0x52C0(t1)        ; alpha
  +0x40 mul.s $f6, $f6, $f8
  +0x44 mul.s $f7, $f7, $f8
  +0x48 add.s $f4, $f4, $f6          ; new stored_yaw
  +0x4C add.s $f5, $f5, $f7          ; new stored_pitch
  +0x50 swc1 $f4, 0x52B8(t1)        ; persist stored
  +0x54 swc1 $f5, 0x52BC(t1)
  +0x58 swc1 $f4, -0x2100(t0)       ; [v19] overwrite camera yaw reg with smoothed
  +0x5C swc1 $f5, -0x20F4(t0)       ; [v19] overwrite camera pitch reg with smoothed
  +0x60 mov.s $f12, $f4
  +0x64 mov.s $f13, $f5
  +0x68 j    0x01176ABC             ; RET
  +0x6C nop

  +0x70 stored_yaw    (seeded from camera at apply)
  +0x74 stored_pitch
  +0x78 alpha = 0.125 = 0x3E000000
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
    (TRAMP + 0x0C, 0x14200016, "bne at, zero, RET(+22)   ; free-roam -> skip"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)       ; cinematic flag"),
    (TRAMP + 0x18, 0x10200013, "beq at, zero, RET(+19)   ; cinematic -> skip"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0x3C09001A, "lui t1, 0x001A           ; scratch base"),
    (TRAMP + 0x24, 0xC52452B8, "lwc1 $f4, 0x52B8(t1)     ; stored_yaw"),
    (TRAMP + 0x28, 0xC52552BC, "lwc1 $f5, 0x52BC(t1)     ; stored_pitch"),
    (TRAMP + 0x2C, 0xC506DF00, "lwc1 $f6, -0x2100(t0)    ; target_yaw"),
    (TRAMP + 0x30, 0xC507DF0C, "lwc1 $f7, -0x20F4(t0)    ; target_pitch"),
    (TRAMP + 0x34, 0x46043181, "sub.s $f6, $f6, $f4      ; delta_yaw"),
    (TRAMP + 0x38, 0x460539C1, "sub.s $f7, $f7, $f5      ; delta_pitch"),
    (TRAMP + 0x3C, 0xC52852C0, "lwc1 $f8, 0x52C0(t1)     ; alpha"),
    (TRAMP + 0x40, 0x46083182, "mul.s $f6, $f6, $f8"),
    (TRAMP + 0x44, 0x460839C2, "mul.s $f7, $f7, $f8"),
    (TRAMP + 0x48, 0x46062100, "add.s $f4, $f4, $f6      ; new stored_yaw"),
    (TRAMP + 0x4C, 0x46072940, "add.s $f5, $f5, $f7      ; new stored_pitch"),
    (TRAMP + 0x50, 0xE52452B8, "swc1 $f4, 0x52B8(t1)     ; persist"),
    (TRAMP + 0x54, 0xE52552BC, "swc1 $f5, 0x52BC(t1)"),
    (TRAMP + 0x58, 0xE504DF00, "swc1 $f4, -0x2100(t0)    ; [v19] cam_yaw = smoothed"),
    (TRAMP + 0x5C, 0xE505DF0C, "swc1 $f5, -0x20F4(t0)    ; [v19] cam_pitch = smoothed"),
    (TRAMP + 0x60, 0x46002306, "mov.s $f12, $f4"),
    (TRAMP + 0x64, 0x46002B46, "mov.s $f13, $f5"),
    (TRAMP + 0x68, 0x0845DAAF, "j 0x01176ABC             ; RET"),
    (TRAMP + 0x6C, 0x00000000, "nop"),
]

SCRATCH_YAW   = TRAMP + 0x70    # 0x001A52B8
SCRATCH_PITCH = TRAMP + 0x74    # 0x001A52BC
SCRATCH_ALPHA = TRAMP + 0x78    # 0x001A52C0

CAM_YAW = 0x0106DF00
CAM_PITCH = 0x0106DF0C
ALPHA_F32 = 0x3E000000          # 0.125


def apply():
    with PineClient() as pc:
        print("[*] Applying v19 (lerp + writeback to camera registers)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        cur_yaw = pc.read_u32(CAM_YAW)
        cur_pitch = pc.read_u32(CAM_PITCH)
        pc.write_u32(SCRATCH_YAW, cur_yaw)
        pc.write_u32(SCRATCH_PITCH, cur_pitch)
        pc.write_u32(SCRATCH_ALPHA, ALPHA_F32)
        print(f"  0x{SCRATCH_YAW:08X} <- 0x{cur_yaw:08X}  stored_yaw seeded")
        print(f"  0x{SCRATCH_PITCH:08X} <- 0x{cur_pitch:08X}  stored_pitch seeded")
        print(f"  0x{SCRATCH_ALPHA:08X} <- 0x{ALPHA_F32:08X}  alpha = 0.125")

        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  Hook B: j 0x001A5248")

        print("[*] Applied. Camera registers now receive smoothed values too.")
        return True


if __name__ == "__main__":
    apply()

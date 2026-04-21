"""v18: Trampoline B adds a temporal lerp to smooth $f12/$f13 frame-to-frame.

The v16 override snapped $f12/$f13 to the camera registers every frame.
When the registers step suddenly (e.g., stop-to-move transitions caused by
the free-roam pad-decode's sensitivity curve), the matrix builder sees a
one-frame jump. User reports these as visible "teleports to target" when
starting a sweep.

v18 softens this by storing the previous frame's $f12/$f13 in scratch
memory and blending toward the camera-register target at 12.5% per frame:

    stored_yaw   += (target_yaw   - stored_yaw)   * alpha   ; alpha = 0.125
    stored_pitch += (target_pitch - stored_pitch) * alpha

Then $f12/$f13 get the smoothed `stored` values. A single-frame register
jump gets spread over ~5 frames and is imperceptible as a teleport.

Layout (26 code instructions + 3 data words at 0x001A5248):

  +0x00 swc1 $f20, 0xb8($sp)        ; restore clobbered
  +0x04 lui  t0, 0x0107
  +0x08 lw   at, -0x3604(t0)        ; mode flag 0x0106C9FC
  +0x0C bne  at, zero, RET(+20)     ; free-roam -> skip override
  +0x10 nop
  +0x14 lw   at, -0x3780(t0)        ; cinematic flag 0x0106C880
  +0x18 beq  at, zero, RET(+17)     ; cinematic -> skip override
  +0x1C nop
  +0x20 lui  t1, 0x001A             ; scratch base
  +0x24 lwc1 $f4, 0x52B0(t1)        ; stored_yaw
  +0x28 lwc1 $f5, 0x52B4(t1)        ; stored_pitch
  +0x2C lwc1 $f6, -0x2100(t0)       ; target_yaw  (camera yaw reg)
  +0x30 lwc1 $f7, -0x20F4(t0)       ; target_pitch (camera pitch reg)
  +0x34 sub.s $f6, $f6, $f4          ; delta_yaw   = target - stored
  +0x38 sub.s $f7, $f7, $f5          ; delta_pitch
  +0x3C lwc1 $f8, 0x52B8(t1)        ; alpha = 0.125
  +0x40 mul.s $f6, $f6, $f8          ; delta_yaw *= alpha
  +0x44 mul.s $f7, $f7, $f8          ; delta_pitch *= alpha
  +0x48 add.s $f4, $f4, $f6          ; stored_yaw += delta*alpha
  +0x4C add.s $f5, $f5, $f7          ; stored_pitch += delta*alpha
  +0x50 swc1 $f4, 0x52B0(t1)        ; persist
  +0x54 swc1 $f5, 0x52B4(t1)
  +0x58 mov.s $f12, $f4              ; $f12 = smoothed yaw
  +0x5C mov.s $f13, $f5              ; $f13 = smoothed pitch
  +0x60 j    0x01176ABC             ; RET
  +0x64 nop

  +0x68 stored_yaw    (init to current camera yaw at apply time)
  +0x6C stored_pitch  (init to current camera pitch)
  +0x70 alpha = 0.125 = 0x3E000000
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

HOOK = 0x01176AB4
HOOK_VAL = 0x08069492

TRAMP = 0x001A5248

PATCHES = [
    (TRAMP + 0x00, 0xE7B400B8, "swc1 $f20, 0xb8($sp)     ; restore clobbered"),
    (TRAMP + 0x04, 0x3C080107, "lui t0, 0x0107"),
    (TRAMP + 0x08, 0x8D01C9FC, "lw at, -0x3604(t0)       ; mode flag"),
    (TRAMP + 0x0C, 0x14200014, "bne at, zero, RET(+20)   ; free-roam -> skip"),
    (TRAMP + 0x10, 0x00000000, "nop"),
    (TRAMP + 0x14, 0x8D01C880, "lw at, -0x3780(t0)       ; cinematic flag"),
    (TRAMP + 0x18, 0x10200011, "beq at, zero, RET(+17)   ; cinematic -> skip"),
    (TRAMP + 0x1C, 0x00000000, "nop"),
    (TRAMP + 0x20, 0x3C09001A, "lui t1, 0x001A           ; scratch base"),
    (TRAMP + 0x24, 0xC52452B0, "lwc1 $f4, 0x52B0(t1)     ; stored_yaw"),
    (TRAMP + 0x28, 0xC52552B4, "lwc1 $f5, 0x52B4(t1)     ; stored_pitch"),
    (TRAMP + 0x2C, 0xC506DF00, "lwc1 $f6, -0x2100(t0)    ; target_yaw"),
    (TRAMP + 0x30, 0xC507DF0C, "lwc1 $f7, -0x20F4(t0)    ; target_pitch"),
    (TRAMP + 0x34, 0x46043181, "sub.s $f6, $f6, $f4      ; delta_yaw"),
    (TRAMP + 0x38, 0x460539C1, "sub.s $f7, $f7, $f5      ; delta_pitch"),
    (TRAMP + 0x3C, 0xC52852B8, "lwc1 $f8, 0x52B8(t1)     ; alpha"),
    (TRAMP + 0x40, 0x46083182, "mul.s $f6, $f6, $f8      ; delta_yaw *= alpha"),
    (TRAMP + 0x44, 0x460839C2, "mul.s $f7, $f7, $f8      ; delta_pitch *= alpha"),
    (TRAMP + 0x48, 0x46062100, "add.s $f4, $f4, $f6      ; stored_yaw += delta"),
    (TRAMP + 0x4C, 0x46072940, "add.s $f5, $f5, $f7      ; stored_pitch += delta"),
    (TRAMP + 0x50, 0xE52452B0, "swc1 $f4, 0x52B0(t1)     ; persist"),
    (TRAMP + 0x54, 0xE52552B4, "swc1 $f5, 0x52B4(t1)"),
    (TRAMP + 0x58, 0x46002306, "mov.s $f12, $f4          ; $f12 = smoothed"),
    (TRAMP + 0x5C, 0x46002B46, "mov.s $f13, $f5          ; $f13 = smoothed"),
    (TRAMP + 0x60, 0x0845DAAF, "j 0x01176ABC             ; RET"),
    (TRAMP + 0x64, 0x00000000, "nop                       [jump delay]"),
]

SCRATCH_YAW   = TRAMP + 0x68    # 0x001A52B0
SCRATCH_PITCH = TRAMP + 0x6C    # 0x001A52B4
SCRATCH_ALPHA = TRAMP + 0x70    # 0x001A52B8

CAM_YAW = 0x0106DF00
CAM_PITCH = 0x0106DF0C
ALPHA_F32 = 0x3E000000          # 0.125


def apply():
    with PineClient() as pc:
        print("[*] Applying v18 (Trampoline B with temporal lerp)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False

        # Initialize scratch storage: seed with current camera values so
        # the first frame doesn't lerp from 0 toward target.
        cur_yaw = pc.read_u32(CAM_YAW)
        cur_pitch = pc.read_u32(CAM_PITCH)
        pc.write_u32(SCRATCH_YAW, cur_yaw)
        pc.write_u32(SCRATCH_PITCH, cur_pitch)
        pc.write_u32(SCRATCH_ALPHA, ALPHA_F32)
        print(f"  0x{SCRATCH_YAW:08X} <- 0x{cur_yaw:08X}  seed stored_yaw from camera")
        print(f"  0x{SCRATCH_PITCH:08X} <- 0x{cur_pitch:08X}  seed stored_pitch from camera")
        print(f"  0x{SCRATCH_ALPHA:08X} <- 0x{ALPHA_F32:08X}  alpha = 0.125")

        # Install hook
        pc.write_u32(HOOK, HOOK_VAL)
        print(f"  0x{HOOK:08X} <- 0x{HOOK_VAL:08X}  Hook B: j 0x001A5248")

        print("[*] Applied. Aim $f12/$f13 now lerp to camera at 12.5% per frame.")
        return True


if __name__ == "__main__":
    apply()

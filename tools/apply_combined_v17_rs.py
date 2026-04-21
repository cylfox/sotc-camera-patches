"""v17-RS (right-stick aim): minimal Trampoline A, no left-stick remap.

Variant of v17 where aim is driven by the right stick instead of the left.
Trampoline A just does the deadzone autofocus-defeat substitute for every
state (free-roam, swim, aim, on-colossus, climbing, ...). Hook B stays
unchanged and overrides $f12/$f13 with the camera yaw/pitch registers,
which are driven by the right stick via the native pad-decode.

End-to-end during aim:
  right-stick X/Y   -> pad-decode stores to s0+0x56/0x57 (untouched)
                   -> camera pad-decode integrates into 0x0106DF00 / 0x0106DF0C
                   -> Hook B loads those into $f12 / $f13 for the aim matrix
  left-stick        -> inert (native aim-yaw/pitch path runs but its output
                                is overridden by Hook B)

Trampoline A layout (7 instructions at 0x001A4984):
  +0x00 addiu at, v0, -0x41        ; shift byte range to [0..0x7E]
  +0x04 sltiu at, at, 0x7F         ; in deadzone?
  +0x08 beq   at, zero, +2         ; outside deadzone -> RET (no substitute)
  +0x0C nop
  +0x10 addiu v0, zero, 0xC0       ; substitute 0xC0 (autofocus defeat, no drift)
  +0x14 j     0x001ACD4C           ; RET
  +0x18 sb    v0, 0x57(s0)         ; delay slot: store final v0
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

TRAMP = 0x001A4984

PATCHES = [
    (TRAMP + 0x00, 0x2441FFBF, "addiu at, v0, -0x41       ; deadzone range shift"),
    (TRAMP + 0x04, 0x2C21007F, "sltiu at, at, 0x7F         ; in [0x41, 0xBF]?"),
    (TRAMP + 0x08, 0x10200002, "beq at, zero, RET(+2)      ; outside -> RET"),
    (TRAMP + 0x0C, 0x00000000, "nop"),
    (TRAMP + 0x10, 0x240200C0, "addiu v0, zero, 0xC0       ; substitute"),
    (TRAMP + 0x14, 0x0806B353, "j 0x001ACD4C               ; RET"),
    (TRAMP + 0x18, 0xA2020057, "sb v0, 0x57(s0)            [delay slot]"),
]


def apply():
    with PineClient() as pc:
        print("[*] Applying v17-RS (right-stick aim, minimal Trampoline A)")
        for a, v, desc in PATCHES:
            pc.write_u32(a, v)
            got = pc.read_u32(a)
            ok = "OK" if got == v else "FAIL"
            print(f"  0x{a:08X} <- 0x{v:08X}  [{ok}]  {desc}")
            if got != v:
                return False
        # Clear v17 trailing bytes (offsets 0x1C..0x4C) that v17-RS doesn't use
        for off in range(0x1C, 0x54, 4):
            pc.write_u32(TRAMP + off, 0)
        print("[*] Applied. Aim now driven by right stick via Hook B.")
        return True


if __name__ == "__main__":
    apply()

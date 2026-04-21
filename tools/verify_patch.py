"""Verify live memory matches the shipped v17 pnach (v17 TrA + v16 TrB)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pine_client import PineClient

EXPECTED = [
    (0x0001ACD44, 0x08069261, "Hook A: j 0x001A4984"),
    (0x0001ACD48, 0x92420107, "Hook A: lbu v0, 0x107(s2)"),
    # Trampoline A (v17, 21 instructions)
    (0x001A4984, 0x3C010107, "TrA: lui at, 0x0107"),
    (0x001A4988, 0x8C21C9FC, "TrA: lw at, -0x3604(at) ; mode flag"),
    (0x001A498C, 0x1420000B, "TrA: bne at, zero, DEADZONE(+11)"),
    (0x001A4990, 0x00000000, "TrA: nop"),
    (0x001A4994, 0x3C010107, "TrA: lui at, 0x0107"),
    (0x001A4998, 0x8C21B484, "TrA: lw at, -0x4B7C(at) ; AIM flag 0x0106B484"),
    (0x001A499C, 0x2421FFFF, "TrA: addiu at, at, -1 ; at = aim - 1"),
    (0x001A49A0, 0x14200006, "TrA: bne at, zero, DEADZONE(+6) ; aim != 1 -> deadzone"),
    (0x001A49A4, 0x00000000, "TrA: nop"),
    (0x001A49A8, 0x92480108, "TrA: lbu t0, 0x108(s2) ; left-X byte"),
    (0x001A49AC, 0xA2080056, "TrA: sb t0, 0x56(s0) ; overwrite right-X scratch"),
    (0x001A49B0, 0x92420109, "TrA: lbu v0, 0x109(s2) ; [v17] v0 = left-Y byte"),
    (0x001A49B4, 0x08069274, "TrA: j 0x001A49D0 (RET)"),
    (0x001A49B8, 0x00000000, "TrA: nop"),
    (0x001A49BC, 0x2441FFBF, "TrA: addiu at, v0, -0x41 (DEADZONE)"),
    (0x001A49C0, 0x2C21007F, "TrA: sltiu at, at, 0x7F"),
    (0x001A49C4, 0x10200002, "TrA: beq at, zero, RET(+2)"),
    (0x001A49C8, 0x00000000, "TrA: nop"),
    (0x001A49CC, 0x240200C0, "TrA: addiu v0, zero, 0xC0"),
    (0x001A49D0, 0x0806B353, "TrA: j 0x001ACD4C (RET)"),
    (0x001A49D4, 0xA2020057, "TrA: sb v0, 0x57(s0) ; [delay; stores left-Y in aim]"),
    # Hook B + Trampoline B (v16, 12 instructions)
    (0x01176AB4, 0x08069492, "Hook B: j 0x001A5248"),
    (0x001A5248, 0xE7B400B8, "TrB: swc1 $f20, 0xb8($sp)"),
    (0x001A524C, 0x3C080107, "TrB: lui t0, 0x0107"),
    (0x001A5250, 0x8D01C9FC, "TrB: lw at, -0x3604(t0) ; mode flag"),
    (0x001A5254, 0x14200006, "TrB: bne at, zero, RET(+6)"),
    (0x001A5258, 0x00000000, "TrB: nop"),
    (0x001A525C, 0x8D01C880, "TrB: lw at, -0x3780(t0) ; cinematic flag"),
    (0x001A5260, 0x10200003, "TrB: beq at, zero, RET(+3)"),
    (0x001A5264, 0x00000000, "TrB: nop"),
    (0x001A5268, 0xC50DDF0C, "TrB: lwc1 $f13, -0x20F4(t0) ; [v16] camera pitch"),
    (0x001A526C, 0xC50CDF00, "TrB: lwc1 $f12, -0x2100(t0) ; camera yaw"),
    (0x001A5270, 0x0845DAAF, "TrB: j 0x01176ABC (RET)"),
    (0x001A5274, 0x00000000, "TrB: nop [jump delay]"),
]

with PineClient() as pc:
    all_ok = True
    for addr, want, desc in EXPECTED:
        got = pc.read_u32(addr)
        ok = got == want
        marker = "OK" if ok else "MISMATCH"
        if not ok:
            all_ok = False
            print(f"  0x{addr:08X}  want=0x{want:08X} got=0x{got:08X}  [{marker}]  {desc}")
        else:
            print(f"  0x{addr:08X}  0x{got:08X}  [OK]  {desc}")
    print()
    print("[*] ALL MATCH" if all_ok else "[!] MISMATCHES FOUND")

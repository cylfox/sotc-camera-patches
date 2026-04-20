# SotC Auto-Focus Disable

A PCSX2 pnach patch for **Shadow of the Colossus (PAL, SCES-53326, CRC `0F0C4A9C`)** that disables the right-stick camera auto-focus ("pitch re-center on release") while preserving:

- Manual pitch and yaw control via the right stick
- Aim cameras for the **bow** and the **sword-to-colossus guide**
- Camera behavior while **climbing colossi**

It does this with a small MIPS trampoline injected into inter-function alignment padding — no large-scale code rewrites, no runtime scripts, no emulator modifications.

---

## Install

### PCSX2 (desktop, v1.7+)

1. Copy `patch/0F0C4A9C_disable_freeroam_autofocus.pnach` into PCSX2's cheats folder.
   (In PCSX2: `Settings` → `Game List` → right-click your SotC PAL entry → `Open Cheats Directory` — or find it via `Documents/PCSX2/cheats/` on Windows.)

2. Enable cheats: `Settings` → `Advanced` → **"Enable Cheats"**.

3. Start the game. The patch applies automatically per-frame via `patch=1` directives, so it's resilient to any game-side memory reinitialization.

Disabling is the reverse: remove or rename the pnach file, or uncheck the "Enable Cheats" toggle.

Modern PCSX2 scans the cheats folder for `<CRC>*.pnach` (glob pattern — see [`pcsx2/Patch.cpp`](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/Patch.cpp)), so the descriptive filename loads automatically.

### NetherSX2 / AetherSX2 (Android)

NetherSX2 is based on a pre-2023 PCSX2 fork, which may require the classic exact-match filename convention. If cheats don't apply:

1. Rename the file to **`0F0C4A9C.pnach`** (drop the descriptive suffix) when copying it to the cheats folder.
2. Path on Android is typically `Android/data/com.github.stenzek.netherSX2/files/cheats/` (or `.../files/cheats_ws/` depending on NetherSX2 build).

The file contents are identical; only the filename matters for the emulator's auto-discovery.

---

## Behavior summary

| State | Before patch | After patch |
|---|---|---|
| Free-roam, release stick after pitch | Camera snaps back to horizontal | **Camera stays where you left it** |
| Free-roam, manual pitch (stick held) | Works | Works |
| Free-roam, manual yaw | Works | Works |
| Hands off controller | Camera sometimes drifts / recenters | **Camera stays still** |
| Climbing a colossus | Works | Works |
| Bow aim (left stick aims) | Works | Works |
| Sword-to-colossus guide | Works | Works |

---

## Repo layout

```
.
├── patch/                    ← the shippable pnach
│   └── 0F0C4A9C_disable_freeroam_autofocus.pnach
├── docs/
│   ├── HOW_IT_WORKS.md       ← technical walkthrough (read this first)
│   └── camera_struct/        ← early struct-mapping artifacts (historical, partly stale)
├── tools/                    ← Python scripts for PINE-based live patching & discovery
│   ├── pine_client.py         — PINE IPC client (TCP 127.0.0.1:28011)
│   ├── apply_trampoline.py    — apply / restore the final patch live
│   ├── patch_live.py          — live-patch a single word for experimentation
│   ├── restore_patch.py       — restore the original pad-read instruction
│   ├── find_free_space.py     — scan code region for inter-function padding
│   ├── find_stable_flags.py   — find memory addresses stable-within-state but different across states (the tool that found the mode flag)
│   ├── read_around_padread.py — disassemble instructions around the hook site
│   ├── poll_flag.py           — high-frequency poll of a single address
│   └── parallel_scan.py       — multi-connection parallel memory scanner
├── archive/                  ← discovery-era scripts + raw capture JSONs
└── README.md
```

---

## Quick start — trying the patch live (without installing the pnach)

Useful for testing changes or exploring. Requires:

- PCSX2 2.6.3+ running the PAL SotC (CRC `0F0C4A9C`)
- PINE IPC enabled in PCSX2 (`Settings` → `Advanced` → "Enable PINE IPC") on TCP port **28011**
- Python 3.10+ on Windows

```cmd
cd tools

REM apply the patch to the running emulator
py apply_trampoline.py

REM restore the original instructions
py apply_trampoline.py restore
```

The apply script verifies the trampoline region is zero before writing, so it's safe to run multiple times.

---

## How it works — short version

The camera's pad-byte read at `0x001ACD44` (`lbu v0, 0x107(s2)`) is hijacked with a `j` to a trampoline in unused code-region padding at `0x001A4984`. The trampoline:

1. Reads a mode flag at `0x0106C9FC` — `1` = free-roam, `0` = bow/sword aim.
2. **In aim mode:** skips all logic and stores the real pad byte unchanged. Aim cameras continue to work normally.
3. **In free-roam mode:** if the real pad byte is in `[0x41, 0xBF]` (the game's neutral deadzone), substitutes `0xC0` (non-neutral for the auto-focus trigger, but below the pitch-input scaling threshold — no drift). Otherwise passes the real byte through so manual pitch input continues to work.

Total: 13 patched words. See `docs/HOW_IT_WORKS.md` for a full technical explanation — the camera-input pipeline, the MIPS assembly walkthrough, and the design rationale.

---

## Porting

The same technique should work for other SotC builds (NTSC-U `877F3436`, NTSC-J, HD remasters). You'll need to re-find:

- The pad-read hook site (a `lbu rN, ??(rM); sb rN, ??(rO)` sequence in the camera-input function)
- An unused run of zero-words for the trampoline
- The auto-focus neutral deadzone and pitch-input thresholds (binary-search via `patch_live.py`)
- The aim-mode flag (use `find_stable_flags.py` against the new build)

The `tools/` scripts are build-agnostic — only the addresses in `apply_trampoline.py` and the shipped pnach would need updating. See the "Porting to Other SotC Builds" section of `docs/HOW_IT_WORKS.md` for details.

---

## Credits

Reverse-engineered in 2026-04 via PCSX2's built-in debugger and PINE IPC.

---

## License

The patch itself (`patch/0F0C4A9C_disable_freeroam_autofocus.pnach`) is a small set of byte-level writes with no original game code — it's essentially a set of coordinates into binary memory. Share freely.

The tools and documentation in this repository: MIT — use, modify, port, fork as you like.

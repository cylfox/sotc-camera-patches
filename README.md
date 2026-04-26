# SotC Camera Patches

> [!IMPORTANT]
> **This is my love letter to TeamICO and this amazing game ❤️**

A PCSX2 pnach patches for **Shadow of the Colossus (PAL, SCES-53326, CRC `0F0C4A9C`)** that fixes several camera behaviors:

- Disable camera **auto-focus** ("pitch re-center on release") in free-roam
- Aim reticle follows the camera view like a **FPS-style centered aim**
- **Velocity cap** clamps angular camera velocity at a lower max for a less "build-up" feel
- Disable black bars during cutscenes (helpful in 16:9 where the bars compound the 4:3-source vertical crop)

> [!NOTE]
> **Tested configuration:** PAL SCES-53326 using **NTSC mode (60 Hz)** selected from the game's selector and **Spanish** as the in-game language. CRC `0F0C4A9C` is the same disc regardless of boot options, so the byte-level patches should apply to any PAL copy

---

## Patches

Five pnach files ship in `patches/` — two **aim-tracking variants** and three **independent components** you can mix freely.

You can learn more about the research by checking the `docs/HOW_IT_WORKS_*` documents.

### Aim-tracking

These bundle the disable free-roam autofocus and the FPS-centered aim. Pick the one that matches the stick you want driving the aim.

| File                                           | Pick it if you want                                                   |
| ---------------------------------------------- | --------------------------------------------------------------------- |
| `0F0C4A9C_aim_tracks_camera_right_stick.pnach` | **Right-stick aim**. Traditional camera/aim input on the right stick. |
| `0F0C4A9C_aim_tracks_camera_left_stick.pnach`  | **Left-stick aim** Camera/aim input on the left stick.                |

> [!WARNING]  
> The two aim-tracking variants share address ranges so **only use one at a time**. They also include the **Disables free-roam camera auto-focus** fix, so do **not** use the patch `disable_freeroam_autofocus.pnach` alongside (Hook A's address range would conflict).

**Behavior changes vs vanilla:**

- **Free-roam:** camera holds position on stick release instead of snapping back to horizontal. Manual pitch/yaw still work.
- **Bow aim entry:** bow direction inherits the current camera yaw and pitch — no snap to Wander's facing, no Y-reset to horizontal.
- **Bow aim sustained:** the same stick that drives the camera also drives the aim (left-stick or right-stick depending on the variant). Reticle stays centered.

### Disable free-roam autofocus

Disables only the camera "pitch re-center on release" behavior in free-roam. Manual pitch/yaw still work; aim cameras, swim, climbing all behave vanilla.

| File                                        | Pick it if you want                                                                                                |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `0F0C4A9C_disable_freeroam_autofocus.pnach` | **Just the autofocus fix** without the FPS-centered aim — the lightest variant if you don't aim with the bow much. |

> [!NOTE]  
> The autofocus fix is already bundled into the aim-tracking variants. Skip this patch if you're loading `aim_tracks_camera_right_stick.pnach` or `aim_tracks_camera_left_stick.pnach` — Hook A's address range would conflict.

### Camera velocity cap

Clamps the camera's angular velocity at a lower maximum. Reduces the "camera builds up speed the longer you push" sensation and the compound speed-up on repeated presses.

| File                                 | Pick it if you want                                                                                                                |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `0F0C4A9C_camera_velocity_cap.pnach` | **Lower max camera speed + less acceleration feel.** Clamps angular-velocity accumulators to ±2.0 rad/s instead of vanilla ±5.236. |

> [!IMPORTANT]  
> Set the **in-game camera sensitivity to its highest setting** when using this patch. The cap clamps the _maximum_ angular velocity; at lower in-game sensitivities the game's stick-to-velocity scale never reaches that ceiling, so the cap has no effect (and behavior across sensitivities feels inconsistent).

**Behavior changes vs vanilla:**

| Axis  | Vanilla max                     | Capped                       |
| ----- | ------------------------------- | ---------------------------- |
| Yaw   | 5.236 rad/s (5π/3 ≈ **300°/s**) | 2.000 rad/s (≈ **115°/s**)   |
| Pitch | 1.396 rad/s (≈ **80°/s**)       | unchanged (cap is above max) |

The game's ramp-up and decay curves are untouched, only the ceiling. SotC normally accumulates angular velocity over time while the stick is held — the camera builds speed the longer you push, and repeated presses in the same direction compound. The cap stops both at the same 2.0 rad/s ceiling.

> [!TIP]  
> If you want finer tuning than the fixed 2.0 cap (growth dampening, aggressive snap-on-release, per-axis independent caps), run `py tools\cap_camera_velocity.py` while playing. The live tool offers three presets (`v1`, `v2`, `v3`) and lets you dial `--cap`, `--growth`, and `--snap-below` in real time.

### Disable cinematic letterbox

Disables the cinematic black bars at the top and bottom of the screen during cutscenes. Useful in 16:9 where PCSX2 already crops vertically and the bars compound that crop and make the cutscene feel over-zoomed.

| File                                         | Pick it if you want                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------------------- |
| `0F0C4A9C_disable_cinematic_letterbox.pnach` | **The full screen during cutscenes** instead of the letterboxed-then-cropped framing. |

> [!NOTE]  
> Removing the bars does **not** widen the cutscene camera FOV — the framing is still 4:3-source. You'll see the parts of the scene the bars were hiding (e.g. character heads/feet near frame edges), which is generally fine but can occasionally reveal geometry the cutscene was framing out.

**How it works:** the cinematic system stores a "bars visible" float at `0x01477504` — `1.0` while bars should be drawn, `0.0` otherwise. The pnach pins it at `0.0` every frame, so the bars never show even when a cutscene tries to enable them. The variable lives in a HUD/UI struct cluster (`0x01477290..0x01477508`).

---

## Controller setup

These patches are better experience by remapping some of the buttons, luckily SotC provides a button remapping option under **Options → Button Configuration**. The remap below moves heavy-use actions (Action, Attack, Grab) onto the shoulder buttons and reassigns the face buttons to camera controls.

| Action          | Default     | Remapped     |
| --------------- | ----------- | ------------ |
| Jump            | _unchanged_ | _unchanged_  |
| Action          | ○ Circle    | **L1**       |
| Control horse   | ✕ Cross     | **R1**       |
| Attack          | ▢ Square    | **L2**       |
| Grab            | R1          | **R2**       |
| View colossus   | L1          | **○ Circle** |
| Next weapon     | _unchanged_ | _unchanged_  |
| Previous weapon | _unchanged_ | _unchanged_  |
| Center camera   | L2          | **▢ Square** |
| Camera zoom     | R2          | **✕ Cross**  |

---

## Known issues

### "Reset camera behind Wander" is broken

The camera patches interfere with the reset-camera-behind-Wander logic as a side-effect of the autofocus-defeat mechanism.

---

## Repo layout

```
.
├── patches/
│   ├── 0F0C4A9C_aim_tracks_camera_left_stick.pnach    ← bundle: left-stick aim
│   ├── 0F0C4A9C_aim_tracks_camera_right_stick.pnach   ← bundle: right-stick aim
│   ├── 0F0C4A9C_disable_freeroam_autofocus.pnach      ← component: free-roam autofocus disable
│   ├── 0F0C4A9C_camera_velocity_cap.pnach             ← component: caps camera yaw+pitch angular velocity at 2.0 rad/s
│   └── 0F0C4A9C_disable_cinematic_letterbox.pnach     ← component: disables cinematic letterbox bars
├── docs/
│   ├── HOW_IT_WORKS_CAMERA_FIX.md    ← aim-tracking walkthrough (autofocus + FPS-aim mechanics)
│   └── HOW_IT_WORKS_VELOCITY_CAP.md  ← velocity-cap pnach walkthrough (independent component)
├── tools/                    ← Python scripts for PINE-based live patching & discovery
│   ├── pine_client.py         — PINE IPC client (TCP 127.0.0.1:28011)
│   ├── boot_trace.py          — timing trace: log memory changes during boot
│   ├── cap_camera_velocity.py — live-tune velocity cap/growth/snap (experimental, beyond what the pnach does)
│   ├── apply_combined_v17.py  — live-apply v17 Trampoline A (left-stick aim)
│   ├── apply_combined_v17_rs.py — live-apply v17 Trampoline A (right-stick aim)
│   ├── apply_aim_center_v16.py  — live-apply v17 Trampoline B (aim matrix override)
│   ├── verify_patch.py        — check that live memory matches the shipped pnach
│   ├── find_stable_flags.py   — stable-diff flag discovery (found 0x0106C9FC, 0x0106AD90, 0x0106B484, 0x0106C880)
│   └── …                      many helper scripts for iteration and diagnosis
├── archive/                  ← raw memory capture JSONs + early discovery scripts
└── README.md
```

---

## Live testing

If you want to test or explore and not use the pnatch files you can use the scripts inside `tools/`.

Requires:

- PCSX2 2.6.3+ running PAL SotC (CRC `0F0C4A9C`)
- PINE IPC enabled in PCSX2 (`Settings` → `Advanced` → "Enable PINE IPC") on TCP port **28011**
- Python 3.10+ on Windows

```cmd
cd tools

REM apply the v17 left-aim default (in-place, no pnach needed):
py apply_combined_v17.py
py apply_aim_center_v16.py

REM verify what's in live memory
py verify_patch.py

REM switch Trampoline A to the right-stick variant without restarting:
py apply_combined_v17_rs.py
```

Apply scripts verify each write and are safe to run repeatedly.

---

## Install

### PCSX2 (desktop, v1.7+)

1. Pick the pnach files you want from `patches/` (see the variants below) and copy them into PCSX2's `PCSX2\patches` folder. The two `aim_tracks_camera_*_stick` bundles are mutually exclusive; the independent components can be combined freely.
2. Start the game. The patch applies automatically per-frame via `patch=1` directives, so it's resilient to any game-side memory reinitialization. You can click on `Tools` → `Reload Cheats/Patches` to reload it if needed.

To disable it remove the pnach file from `PCSX2\patches` folder, or uncheck "Enable Cheats".

Modern PCSX2 scans the cheats folder for `<CRC>*.pnach` (glob pattern — see [`pcsx2/Patch.cpp`](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/Patch.cpp)), so any of the descriptive filenames below load automatically.

### NetherSX2 / AetherSX2 (Android)

NetherSX2 is based on a pre-2023 PCSX2 fork which may require the classic exact-match filename convention. If cheats don't apply:

1. Copy the patch file into your device's internal memory or SD card
2. Launch the game. In the game's emulator options go to `Patch Codes` → `Add Patch` → `Import from file` And select the pnach file

---

## Porting

The same technique should work for other SotC builds (NTSC-U `877F3436`, NTSC-J, HD remasters). You'll need to re-find:

- The pad-read hook site (an `lbu rN, ??(rM); sb rN, ??(rO)` sequence in the camera-input function)
- An unused run of zero-words for the trampolines (use `tools/find_free_space.py`)
- The auto-focus neutral deadzone and pitch-input thresholds (binary-search via a live-patch script)
- The state flags (`find_stable_flags.py` against the new build) — mode flag, aim flag, cinematic flag
- The camera yaw/pitch registers (adjacent to the yaw register typically; `snap_pitch.py` helps)
- The aim-matrix builder function prologue (for Hook B)

The `tools/` scripts are mostly build-agnostic — only the addresses in the apply scripts and the shipped pnach would need updating. See the "Porting to Other SotC Builds" section of `docs/HOW_IT_WORKS_CAMERA_FIX.md` for details.

---

## Credits

Reverse-engineered by **[cylfox](https://github.com/cylfox)** in 2026-04 via PCSX2's built-in debugger and PINE IPC.

Last updated: 2026-04-26.

---

## License

The patches themselves (files under `patches/`) are byte-level writes with no original game code — coordinates into binary memory. Share freely.

The tools and documentation in this repository: MIT — use, modify, port, fork as you like.

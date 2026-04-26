# SotC Camera Fix

> **This is my love letter to TeamICO and this amazing game ❤️**

A PCSX2 pnach patch for **Shadow of the Colossus (PAL, SCES-53326, CRC `0F0C4A9C`)** that fixes several camera behaviors:

- Disables the right-stick camera **auto-focus** ("pitch re-center on release") in free-roam
- Fixes the **swim** camera (right-stick drives camera, left-stick drives Wander only)
- Fixes **on-colossus** and **climbing** camera behavior to match free-roam feel
- Adds **FPS-style centered aim** (the aim reticle follows the camera view) with pitch inheritance on aim entry
- Bails out of all overrides during **cinematics** so scripted cutscene cameras aren't hijacked

Plus two optional independent pnach files:

- **Velocity cap** — clamps angular camera velocity at a lower max for a less "build-up" feel
- **No letterbox** — disables the cinematic black bars at the top/bottom of the screen during cutscenes (helpful in 16:9 where the bars compound the 4:3-source vertical crop)

Implemented as two MIPS trampolines injected into inter-function alignment padding. No large-scale code rewrites, no runtime scripts, no emulator modifications.

> **Tested configuration:** PAL SCES-53326 using **NTSC mode (60 Hz)** selected from the game's selector and **Spanish** as the in-game language. CRC `0F0C4A9C` is the same disc regardless of boot options, so the byte-level patches should apply to any PAL copy — but if you run into anything that behaves differently, this is the bench the patch was verified on.

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

## Pick your variant

Five pnach files ship in `patches/` — two **aim-tracking variants** (full bundles, pick at most one) and three **independent components** you can mix freely.

### Aim-tracking variants (pick at most ONE — full bundles)

These bundle every camera fix into a single pnach: free-roam autofocus defeat, swim / climbing / on-colossus state fixes, FPS-centered aim with pitch inheritance, and cinematic bail-out. Pick the one that matches the stick you want driving the aim.

| File                                                | Pick it if you want                                                                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `0F0C4A9C_aim_tracks_camera_left_stick.pnach`       | **Left-stick aim** (default). Unified yaw+pitch on the left stick during bow-aim. Reticle stays centered.                                    |
| `0F0C4A9C_aim_tracks_camera_right_stick.pnach`      | **Right-stick aim**. Traditional camera/aim input on the right stick; left stick inert in aim.                                               |

The two aim-tracking variants share address ranges — only one at a time. They also include the autofocus-defeat fix internally, so do **not** also load `disable_freeroam_autofocus.pnach` alongside (Hook A's address range would conflict).

### Independent components (mix freely)

Each component is a single-feature patch that touches its own non-overlapping address range. Combine any subset. The autofocus-defeat one is the same fix that's already inside the aim-tracking bundles — load it on its own only if you don't want the FPS-aim feature.

| File                                              | What it does                                                                                                                              |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `0F0C4A9C_disable_freeroam_autofocus.pnach`       | **Disables free-roam camera auto-focus** (the "pitch re-center on release" behavior). Manual pitch/yaw still work. Aim cameras untouched. Skip this if you're loading an `aim_tracks_camera_*_stick` bundle. |
| `0F0C4A9C_camera_velocity_cap.pnach`              | **Lower max camera speed + less acceleration feel.** Clamps the game's angular-velocity accumulators to ±2.0 rad/s instead of the vanilla ±5.236. Reduces the "camera builds up speed the longer you push" sensation. |
| `0F0C4A9C_disable_cinematic_letterbox.pnach`      | **Disables the cinematic black bars** at the top/bottom of the screen during cutscenes. Useful in 16:9 where PCSX2 already crops vertically; the bars compound that crop and make the cutscene feel over-zoomed. |

### Velocity cap details

> **Set in-game camera sensitivity to its highest setting** when using the velocity cap. The cap clamps the *maximum* angular velocity; at lower in-game sensitivities the game's stick-to-velocity scale never reaches that ceiling, so the cap has no effect (and behavior across sensitivities feels inconsistent). Highest sensitivity gives the cap something to clamp against on every push, which is when it does what it's supposed to.

### Letterbox-disable details

> **Side-effect note:** removing the bars does not widen the cutscene camera FOV — the framing is still 4:3-source. You'll see the parts of the scene the bars were hiding (e.g., character heads/feet near frame edges), which is generally fine but can occasionally reveal geometry the cutscene was framing out.

### Behavior summary (aim-tracking variants)

| State                                  | Vanilla                                                   | Patch (aim-tracking variants)                                                              |
| -------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Free-roam, release stick               | Camera snaps back to horizontal                           | **Camera holds position**                                                                  |
| Free-roam, manual yaw/pitch            | Works                                                     | Works                                                                                      |
| Swim                                   | Left stick drives both PJ and camera (noisy)              | **Right stick → camera, left stick → PJ only**; autofocus disabled                         |
| On top of a colossus                   | Left stick affects camera weirdly                         | **Right stick → camera, left stick inert**                                                 |
| Climbing a colossus                    | Left stick affects camera weirdly                         | **Right stick → camera**                                                                   |
| Bow aim (entry)                        | Camera snaps to align with Wander, Y resets to horizontal | **Camera direction is preserved; aim inherits yaw AND pitch from the camera on entry**     |
| Bow aim (sustained, left-stick variant)  | Left stick aims, camera follows                           | **Left stick drives both yaw and pitch of aim; reticle stays centered**                    |
| Bow aim (sustained, right-stick variant) | Left stick aims, camera follows                           | **Right stick drives both yaw and pitch of aim; reticle stays centered, left stick inert** |
| Cinematics                             | Work                                                      | Work — scripted cutscene cameras are not hijacked                                          |

### Behavior summary (velocity cap)

SotC accumulates angular velocity over time while the right stick is held — the camera gets faster the longer you push, and repeated presses in the same direction compound because decay between presses doesn't fully complete. The velocity-cap patch clamps the game's two velocity accumulators to a lower max without changing the game's ramp or decay rates.

| Axis  | Vanilla max speed               | Capped                       | Effect                                                                                                         |
| ----- | ------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Yaw   | 5.236 rad/s (5π/3 ≈ **300°/s**) | 2.000 rad/s (**≈ 115°/s**)   | Camera stops "building up" past a comfortable max. Repeat-press compounding is capped at the same 2.0 ceiling. |
| Pitch | 1.396 rad/s (≈ **80°/s**)       | Unchanged (cap is above max) | No visible change.                                                                                             |

> The cap is **only consistently effective at the in-game maximum camera sensitivity setting**. Lower sensitivities scale stick input down before the velocity accumulator integrates, so the accumulator never reaches the 2.0 rad/s ceiling and the cap has nothing to clamp. Use highest sensitivity (Options → Camera) for the patch to behave the same way every push.

See **[`docs/HOW_IT_WORKS_VELOCITY_CAP.md`](docs/HOW_IT_WORKS_VELOCITY_CAP.md)** for the full walkthrough — addresses touched, trampoline assembly, word-by-word vanilla-vs-patched table, and RE notes.

### Behavior summary (no letterbox)

The cinematic system stores a "bars visible" float at `0x01477504`: `1.0` while bars should be drawn, `0.0` otherwise. The pnach pins it at `0.0` every frame, so the bars never show even when a cutscene tries to enable them. The variable lives in a HUD/UI struct cluster (`0x01477290..0x01477508`); other values in that struct (animated HUD overlays, prompts) are not touched.

> If you want finer tuning than the fixed 2.0 cap (growth dampening, aggressive snap-on-release, per-axis independent caps), run `py tools\cap_camera_velocity.py` while playing. The live tool offers three presets (`v1`, `v2`, `v3`) and lets you dial `--cap`, `--growth`, and `--snap-below` in real time. See the tool's header for details.

---

## Controller setup (recommended for the `aim_tracks_camera_right_stick` variant)

If you're using **`0F0C4A9C_aim_tracks_camera_right_stick.pnach`** on a modern controller where the right stick is your main camera input and the triggers are your main "press-and-hold" inputs, the vanilla SotC button layout doesn't map cleanly to muscle memory from other games. A small PCSX2 controller remap makes the patch much more ergonomic:

- Map physical **L2 trigger → virtual Square** (action / draw bow / grab / pick up / release)
- Map physical **R2 trigger → virtual Cross** (jump / grip boost)

Do this in **PCSX2: Settings → Controllers → your pad → Bindings**. You don't need to remove the original Square/Cross face-button bindings; you can add L2/R2 as _additional_ inputs for the same virtual buttons.

---

## Known issues

### Aim direction-reversal flicker (aim-tracking variants)

Both aim-tracking variants have an occasional camera "teleport/flicker" visible during aim on **direction reversal** (e.g., snapping the stick from full right to full left). It's a one-frame step of ~1.5° rotation, documented in detail in `docs/HOW_IT_WORKS_CAMERA_FIX.md`. It's less pronounced in the right-stick variant (or that's my perception).

If it bothers you fall back to `0F0C4A9C_disable_freeroam_autofocus.pnach` (no FPS-aim features, vanilla aim) or use the **velocity cap patch**.

### L2's "reset camera behind Wander" is broken (all variants)

In vanilla SotC, holding **L2 re-centers the camera behind Wander**. **This patch disables that behavior** — holding L2 does nothing for the camera. Both `disable_freeroam_autofocus.pnach` and the two aim-tracking variants interfere with the reset-camera-behind-Wander logic as a side-effect of the autofocus-defeat mechanism.

If you rely on L2's camera reset in vanilla, it won't work with this patch active. The recommended **L2-as-Square remap** (see Controller setup above) effectively repurposes L2 so you aren't missing the functionality — L2 becomes a useful "press to interact/draw bow" instead of a no-op.

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

## Quick start — trying the patch live (without installing the pnach)

Useful for testing changes or exploring. Requires:

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

## How it works — short version

Two coordinated hooks, both in inter-function zero padding:

1. **Hook A** at `0x001ACD44` (camera pad-read) → Trampoline A at `0x001A4984`. Depending on the state flags at `0x0106C9FC` (mode) and `0x0106B484` (bow-aim), either substitutes a `0xC0` byte into the right-stick-Y scratch slot (defeats free-roam autofocus) or remaps left-stick bytes into the right-stick scratch slots (so the left stick drives the camera via the native camera pad-decode).

2. **Hook B** at `0x01176AB4` (aim matrix builder prologue) → Trampoline B at `0x001A49A0` for right-stick / `0x001A49D8` for left-stick (both inside the same `0x001A4984` padding region as Trampoline A). When `0x0106C9FC = 0` (non-free-roam) and `0x0106C880 ≠ 0` (not in a cinematic), overrides the aim-direction matrix inputs `$f12` (yaw) and `$f13` (pitch) with the live camera registers `0x0106DF00` / `0x0106DF0C`. Result: the aim direction tracks the camera view, reticle stays centered.

See `docs/HOW_IT_WORKS_CAMERA_FIX.md` for the full technical walkthrough — the camera-input pipeline, the MIPS assembly, how the state flags were discovered, and the design rationale.

> **Velocity-cap pnach** is documented in its own walkthrough — it's a different patch into a different part of the game (the camera velocity-update function), with no overlap with the aim-tracking variants' hook sites or trampoline region. See **[`docs/HOW_IT_WORKS_VELOCITY_CAP.md`](docs/HOW_IT_WORKS_VELOCITY_CAP.md)**.

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

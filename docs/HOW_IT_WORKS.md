# How the SotC Camera-Fix Patch Works

A technical walkthrough of the Shadow of the Colossus (PAL, SCES-53326) camera-input pipeline and how the shipped patch modifies it. The v1 walkthrough (sections 1–10 below) is the foundation — it covers the original autofocus defeat and is still accurate for the pad-read mechanics. Current shipped behavior is v17 Trampoline A + v16 Trampoline B ("unified left-stick camera during aim"), summarized in §0.

---

## 0. What the current patch (`0F0C4A9C_camera_fix_v17_left_aim.pnach`) actually does

Two hooks with three shared state flags and three memory reads (yaw, pitch, mode). Per-state behavior matrix:

| State       | mode flag `0x0106C9FC` | aim flag `0x0106B484` | cinematic flag `0x0106C880` | Hook A (pad-read)                      | Hook B (aim matrix)   |
| ----------- | ---------------------- | --------------------- | --------------------------- | -------------------------------------- | --------------------- |
| Free-roam   | 1                      | 0                     | 1                           | deadzone substitute (autofocus defeat) | skipped               |
| Swim        | 0                      | 0                     | 1                           | deadzone substitute                    | applied (yaw + pitch) |
| On colossus | 0                      | 0                     | 1                           | deadzone substitute                    | applied               |
| Climbing    | 0                      | **2**                 | 1                           | deadzone substitute                    | applied               |
| Bow aim     | 0                      | **1**                 | 1                           | left-X → right-X scratch remap         | applied (yaw + pitch) |
| Cinematic   | 0                      | 0                     | **0**                       | deadzone substitute                    | **skipped (v14)**     |

**Hook A (Trampoline A at `0x001A4984`, 21 instructions)** — redirects the pad-byte decode. The remap path fires **only** when the aim flag equals exactly `1`. In aim both axes of the left stick get remapped into the right-stick scratch slots (`s0+0x56` gets left-X, `s0+0x57` gets left-Y via a RET-delay-slot trick). Every non-aim state falls through to the deadzone substitute, so autofocus is defeated consistently across free-roam, swim, on-colossus, climbing, and any future non-aim state we haven't sampled.

**Hook B (Trampoline B at `0x001A5248`, 12 instructions)** — overrides **both** aim-direction matrix inputs with live camera state: `$f12` from the camera yaw register (`0x0106DF00`) and `$f13` from the camera pitch register (`0x0106DF0C`). So the reticle tracks the camera view in both axes (FPS-style centered aim + pitch inheritance on entry). The override is suppressed in free-roam (no aim camera to track) and suppressed during cinematics (v14 cinematic-bail gate).

**End-to-end during aim**: left-stick X/Y → Trampoline A remap → scratch slots `s0+0x56` / `s0+0x57` → game's free-roam pad-decode → camera yaw/pitch registers `0x0106DF00` / `0x0106DF0C` → Hook B override of `$f12`/`$f13` → aim matrix builder → reticle tracks camera. The right stick is effectively unused in aim (its scratch slots are overwritten by the left-stick remap).

**Known caveat (v17)**: occasional camera "teleport" visible during aim, specifically on **direction reversal** (e.g. pushing the stick from full right to full left). Three rounds of investigation spanning seven distinct fix attempts (v18/v19 smoothing `$f12`/`$f13`, v20 smoothing direction buffer, v21 clamping at the atan2 writer, v22 forcing a reference vector to break feedback, v23 MIPS counter-based override toggle, plus Python hammer and Python toggle approaches) all either did nothing, broke aim orientation, froze the game, or produced a camera-vs-aim fight. We've now positively identified the jump location (`0x0106E7C0` rendered forward, driven from `0x0106C230` direction buffer via VU0 transform at `0x0125A5C8`), disassembled the matrix builder at `0x01176AA0`, and confirmed a feedback loop where the direction buffer is read as input AND written as output each frame. The proper fix requires PCSX2's debugger to single-step into `0x001B47F0` / `0x001B3F08` and identify an upstream "target" aim-direction writer that we haven't yet mapped. Mild enough that v17 left-stick is the shipped default; the right-stick variant `patch/0F0C4A9C_camera_fix_v17_right_aim.pnach` is available as an alternative for anyone who finds the flicker intolerable (the flicker is likely reduced or gone there since Trampoline A has no left-stick remap interacting with the matrix-builder feedback loop).

**Flag semantics** (stable-state diffed via `tools/find_stable_flags.py` + `tools/diff_aim_vs_all.py` / `diff_cinematic.py`):

- `0x0106C9FC` — free-roam indicator. `1` in free-roam, `0` otherwise.
- `0x0106B484` — bow-aim indicator. `1` in bow-aim only; `0` in free-roam/swim/on-colossus; `2` while climbing. Gate uses strict `== 1`.
- `0x0106C880` — gameplay indicator. `1` during gameplay (all states we've sampled), `0` during cinematic cutscenes.

**Register reads** (all offsets from the `0x01070000` base loaded by the trampolines' `lui t0, 0x0107`):

- `0x0106DF00` — camera yaw (radians). Driven by right-stick-X native pad-decode, also by left-X via Trampoline A remap during aim.
- `0x0106DF0C` — camera pitch (radians, range ≈ ±1.22 / ±70°). Driven by right-stick-Y native pad-decode.

The original v1 walkthrough below (sections 1–10) remains accurate for the pad-read mechanics and the MIPS trampoline technique. The v17 additions (aim flag gate at `0x0106B484`, cinematic flag at `0x0106C880`, camera-pitch register `0x0106DF0C`, two-axis left-stick remap in Trampoline A, aim-matrix `$f12`/`$f13` override in Trampoline B) follow the same hook-and-trampoline pattern.

### Available variants

Three pnach files ship in `patch/`. They all share the same CRC so **only one of the full-featured variants should be active in PCSX2's cheats folder at a time** — they conflict at Trampoline A / Hook B address ranges:

- **`0F0C4A9C_camera_fix_v17_left_aim.pnach`** — main v17, **left-stick aim** (unified yaw + pitch on left stick, right stick unused in aim). The configuration the matrix above describes.
- **`0F0C4A9C_camera_fix_v17_right_aim.pnach`** — v17-RS, **right-stick aim** (traditional camera/aim input on right stick, left stick inert in aim). Trampoline A shrinks from 21 to 7 words (no left-X/Y remap); Hook B unchanged. All other features (autofocus defeat, swim fix, climbing fix, on-colossus fix, cinematic bail, pitch inheritance) are identical. Pick this one if you prefer right-stick aim, or if the direction-reversal flicker in the left-stick variant bothers you — the reversal flicker likely originates from Trampoline A's remap interacting with the matrix builder's feedback loop and is reduced or gone in v17-RS.
- **`0F0C4A9C_camera_fix_v1_disable_freeroam_autofocus.pnach`** — the original v1, **autofocus-only**. Just disables the free-roam right-stick auto-recenter (13 patches at `0x001A4984`); aim cameras, swim, climbing all behave vanilla. Useful if you only want the original autofocus-defeat feature without any of the FPS-aim changes.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [The Game's Camera-Input Pipeline](#2-the-games-camera-input-pipeline)
3. [The Pad-Read Function](#3-the-pad-read-function)
4. [How Auto-Focus Is Triggered](#4-how-auto-focus-is-triggered)
5. [What the Patch Does](#5-what-the-patch-does)
6. [The Trampoline Mechanics (MIPS)](#6-the-trampoline-mechanics-mips)
7. [The Mode-Flag Bypass](#7-the-mode-flag-bypass)
8. [Why These Specific Values](#8-why-these-specific-values)
9. [What This Reveals About SotC's Camera](#9-what-this-reveals-about-sotcs-camera)
10. [Porting to Other SotC Builds](#10-porting-to-other-sotc-builds)

---

## 1. The Problem

Shadow of the Colossus has an **auto-focus** (sometimes called "auto-center") feature on its camera: whenever the player releases the right analog stick in free-roam, the camera automatically pitches back toward a neutral horizontal view. This is intended as a convenience but many players find it disorienting — the camera moves without their input, often fighting against what they want to see.

**Goal:** disable this auto-centering while keeping:

- Manual right-stick pitch control (up/down)
- Right-stick yaw control (left/right)
- Camera behavior in special modes (bow aim, sword-to-colossus guide, climbing, cutscenes)

---

## 2. The Game's Camera-Input Pipeline

SotC's right-stick camera control flows through several layers before reaching the rendered camera pose. From hardware to screen:

```
  Hardware pad       ---+
                        |
                        v
  Raw pad buffer     (in EE RAM; per-port byte stream with stick axes
                      at specific offsets)
                        |
                        v
  Pad-decode function   <-- THIS IS WHERE THE PATCH HOOKS
  at 0x001ACD44..
  (reads bytes 0x104..0x10B, stores decoded copies into a scratch struct)
                        |
                        v
  Camera-input
  normalization   ---------> converts raw bytes to ±1.0 floats
                        |
                        v
  Virtual-stick
  memory at 0x0106C0FC/100
                        |
                        v
  Rotation compute     (VU0 macro-mode math at 0x0142B398 — not EE-readable)
                        |
                        v
  Camera pose struct at 0x0106E5D0
  (position, forward, up, view matrix)
                        |
                        v
  Render / transform pipeline (0x0118E030..0x0118F3F0)
                        |
                        v
  Display
```

**Key observations from the reverse-engineering session:**

- The actual "auto-focus rotation delta" is computed inside **VU0 macro-mode** instructions. VU registers are not accessible from the EE-side (where PINE IPC lives), so we cannot observe or patch the rotation math directly.
- The **output** side of the pipeline (camera pose, render transforms) is readable and writable, but patching there breaks general camera state — it's downstream of all the logic we want to modify.
- The **input** side (pad decode) is the earliest EE-accessible point where we can influence the camera without touching VU state.

This is why the patch lives at the pad-decode level, not deeper in the pipeline.

---

## 3. The Pad-Read Function

The camera-input path begins at address `0x001ACD44` with this instruction:

```
0x001ACD44  lbu v0, 0x107(s2)    ; load unsigned byte from [s2 + 0x107] into v0
0x001ACD48  sb  v0, 0x57(s0)     ; store v0 into [s0 + 0x57]
0x001ACD4C  lbu v1, 0x108(s2)    ; next byte
0x001ACD50  sb  v1, 0x54(s0)
0x001ACD54  lbu v0, 0x109(s2)    ; ...
0x001ACD58  jal 0x001AEBD0
0x001ACD5C  sb  v0, 0x55(s0)     ; delay slot
```

In human terms: the function reads four consecutive bytes from the pad buffer (pointed to by `$s2`) and stores them into a "decoded pad state" scratch struct (pointed to by `$s0`), possibly reordering them.

**Pad-byte layout (per-frame pad state):**

| Pad offset | Meaning                                           |
| ---------- | ------------------------------------------------- |
| +0x106     | (stick X — not our target)                        |
| +0x107     | **right-stick Y** (this is what we hook)          |
| +0x108     | (stick X again or other axis — context-dependent) |
| +0x109     | additional pad byte                               |

**Byte values (confirmed experimentally):**

- `0x80` = center/neutral
- `0xFF` = full up
- `0x00` = full down

The game treats a **range around 0x80** as "neutral" for the purpose of detecting "user has released the stick." This range (the **game's neutral-detection deadzone**) is approximately `[0x41, 0xBF]` — anything in that range is treated as "released," anything outside is treated as "held."

There's a separate, **smaller pitch-input scaling threshold** around `[0xE0, 0xFF]` for "up" and `[0x00, 0x20]` for "down." Byte values between the two thresholds (e.g., `0xC0`) are registered as "non-neutral" (so auto-focus doesn't fire) but also don't produce actual pitch motion.

That gap is the magic window the patch exploits.

---

## 4. How Auto-Focus Is Triggered

The exact triggering code lives in VU0 space so we never disassembled it, but from observed behavior the mechanism is:

```pseudo
if real_stick_byte is in game's neutral deadzone:
    # the stick is "released"
    camera_pitch_target = horizontal_forward
    camera_pitch = lerp(camera_pitch, camera_pitch_target, decay_rate * dt)
else:
    # the stick is "held"
    camera_pitch_target = current_stick_derived_pitch
    # (no lerp toward horizontal; stick directly drives pitch)
```

This is a **lerp-to-target** model, not a delta-accumulation model. The `target` is what resets on release; the `current` lerp-follows the target. Killing the triggering condition ("release detection") prevents `target` from snapping back to horizontal, which means the lerp has nothing to pull toward, and the camera stays wherever the user left it.

---

## 5. What the Patch Does

At a high level, the patch intercepts the pad-read at `0x001ACD44` and conditionally rewrites the byte value before the game's logic ever sees it.

**Rules applied by the patched code:**

1. **If in bow-aim or sword-guide mode** (detected via a mode flag — see §7): don't modify anything, pass through. Aim cameras keep working normally.

2. **If in free-roam mode, and the real byte is in `[0x41, 0xBF]`** (the game's neutral deadzone): substitute `0xC0`. This:
   - is **outside** the neutral deadzone, so auto-focus never triggers
   - is **below** the pitch-input scaling threshold, so the camera doesn't drift up

3. **If in free-roam mode, and the real byte is outside `[0x41, 0xBF]`** (the player is actually holding the stick to pitch the camera): pass through unchanged. Manual pitch control works normally.

The result is a camera that:

- Stays still when the player releases the stick (auto-focus defeated)
- Responds normally when the player pitches or yaws
- Behaves correctly in special camera modes

---

## 6. The Trampoline Mechanics (MIPS)

### Why a trampoline and not an in-place rewrite

The original code has the byte read immediately followed by its use:

```
0x001ACD44  lbu v0, 0x107(s2)    ; reads byte
0x001ACD48  sb  v0, 0x57(s0)     ; uses v0 immediately — no free instruction slot
```

A conditional check (`if byte in range, substitute`) requires at least 3-4 instructions. There's no room between the load and the store, and cascade-rewriting the rest of the function is risky.

Solution: divert execution to a **trampoline** — a separate block of code hosted in unused memory — do the logic there, then jump back.

### Where the trampoline lives

PCSX2's memory scanner (`find_free_space.py`) found thousands of runs of zero-words in the code region — these are alignment padding between functions. We chose `0x001A4984`, which has 39 consecutive zero-words (156 bytes) available. That's 33 KB from the hook site — well within MIPS `j`-instruction reach (which can jump anywhere in the same 256 MB segment).

### The hook

Two instructions at the hook site:

```
0x001ACD44  j 0x001A4984         ; encoded 0x08069261
0x001ACD48  lbu v0, 0x107(s2)    ; encoded 0x92420107
```

The MIPS `j` instruction has a **delay slot** — the instruction at PC+4 executes _before_ the jump transfers control. We exploit this by putting the original `lbu v0, 0x107(s2)` in the delay slot: the real pad byte gets loaded into `$v0` at the same moment we jump to the trampoline.

So when the trampoline begins executing, `$v0` already holds the real pad byte, and the trampoline can check it and modify it.

### The trampoline body (11 instructions)

```
0x001A4984  lui   at, 0x0107           ; at = 0x01070000
0x001A4988  lw    at, -0x3604(at)      ; at = mem[0x0106C9FC]  (mode flag)
0x001A498C  beq   at, zero, +6         ; aim mode? skip to the j below
0x001A4990  nop                        ; delay slot
0x001A4994  addiu at, v0, -0x41        ; at = v0 - 0x41
0x001A4998  sltiu at, at, 0x7F         ; at = 1 if (v0 in [0x41, 0xBF]) else 0
0x001A499C  beq   at, zero, +2         ; outside deadzone? skip substitute
0x001A49A0  nop                        ; delay slot
0x001A49A4  addiu v0, zero, 0xC0       ; v0 = 0xC0 (the substitute)
0x001A49A8  j     0x001ACD4C           ; return past the original sb
0x001A49AC  sb    v0, 0x57(s0)         ; delay slot: store final v0
```

**Walkthrough of the three execution paths:**

1. **Aim mode (mode flag == 0):**
   - `lui at, 0x0107` + `lw at, -0x3604(at)` loads `mem[0x0106C9FC]` into `$at`
   - `beq at, zero, +6` branches to `0x001A49A8` (the `j` return)
   - Delay slot `nop` runs
   - `j 0x001ACD4C` jumps back to the instruction _after_ the original `sb v0, 0x57(s0)`
   - `sb v0, 0x57(s0)` (the `j`'s delay slot) stores the **real, unmodified** `$v0`
   - Result: real pad byte is stored, no substitution happens

2. **Free-roam mode, byte in deadzone:**
   - Mode check passes (flag == 1, so beq not taken)
   - `addiu at, v0, -0x41` shifts the byte range
   - `sltiu at, at, 0x7F` tests if it's in `[0x41, 0xBF]`: yes → `$at = 1`
   - `beq at, zero, +2` not taken
   - Delay slot `nop` runs
   - `addiu v0, zero, 0xC0` **substitutes** `$v0 = 0xC0`
   - `j 0x001ACD4C` jumps back
   - `sb v0, 0x57(s0)` stores `0xC0`
   - Result: auto-focus defeated

3. **Free-roam mode, byte outside deadzone (real pitch input):**
   - Mode check passes
   - Deadzone check fails: `$at = 0`
   - `beq at, zero, +2` **is taken**, branch to `0x001A49A8`
   - Delay slot `nop` runs
   - `j 0x001ACD4C` jumps back
   - `sb v0, 0x57(s0)` stores the **real** `$v0`
   - Result: player's pitch input passes through

### The delay slots

MIPS has two types of delay slots, both exploited here:

- **Jump delay slot** (after `j`): the instruction at PC+4 always executes before the jump. Used at the hook site to do the pad read, and at the trampoline's return to do the store.
- **Branch delay slot** (after `beq`/`bne`): the instruction at PC+4 always executes regardless of whether the branch is taken. Used as `nop` padding to keep the branch target arithmetic simple.

On the R5900 EE, the CPU interlocks load instructions — the loaded value is available on the next cycle. This is why `lw at` immediately followed by `beq at` works without a pipeline stall.

---

## 7. The Mode-Flag Bypass

### Why we need one

Without a mode check, the trampoline substitutes `0xC0` whenever the pad byte is near neutral — even during bow-aim or sword-guide mode. In those modes, the camera is supposed to track the aim direction derived from the left stick. The forced `0xC0` on the right-stick-Y byte breaks that tracking.

(Exact mechanism is speculative: probably the aim camera's "pitch-follow" logic interprets the scratch byte at `s0+0x57` as a pitch offset. When we force it to 0xC0 permanently, the aim camera is stuck applying a constant offset, which conflicts with the aim-direction update.)

### Finding the flag

The aim-mode state has to be represented _somewhere_ in EE memory. The search approach:

1. Take **20 memory snapshots over 2 seconds** in free-roam idle. Keep only addresses whose value stayed constant across all 20 samples (this filters out per-frame toggles and counters).
2. Do the same in bow-aim state.
3. Compare the two "stable maps." Addresses that are stable in both states but have _different_ values are candidate mode flags.

Result: **646 candidate addresses**, many of them clean 0↔1 integer flags in the `0x0106A000..0x0106E000` region (the camera config / input state area).

The chosen flag — `0x0106C9FC` — has value `1` in free-roam and `0` in aim. A separate poll verified stability: only 1 flip in 55086 samples over 3 seconds in a single state (i.e., effectively constant).

### Why stable sampling was necessary

An earlier attempt used a naive diff of single snapshots. It found "candidates" that flickered between values every frame — those were per-frame toggles, not mode flags. The game has many such toggles (animation counters, alternating-buffer indices, frame-phase bits), and they pollute a single-snapshot diff.

Sampling across 2 seconds and requiring stability eliminates that noise. Only values that are genuinely constant within the state survive.

### How the trampoline checks it

Three instructions at the start:

```
lui  at, 0x0107              ; at = 0x01070000
lw   at, -0x3604(at)         ; at = mem[0x01070000 - 0x3604] = mem[0x0106C9FC]
beq  at, zero, +6            ; if at == 0 (aim), skip the substitute logic
```

The offset `-0x3604` is the difference from `0x01070000` to our flag address, sign-extended as a 16-bit immediate for `lw`. This is MIPS's standard "lui + lw" idiom for accessing absolute addresses not easily reachable with small offsets.

---

## 8. Why These Specific Values

### The substitute value `0xC0`

Binary-searched experimentally by live-patching `addiu v0, zero, IMM` for various IMM values and observing camera behavior:

| IMM      | Auto-focus on release       | Upward drift      |
| -------- | --------------------------- | ----------------- |
| 0x7F     | **fires** (seen as neutral) | none              |
| 0x90     | fires                       | none              |
| 0xB0     | fires                       | none              |
| **0xC0** | **suppressed**              | **none**          |
| 0xE0     | suppressed                  | none              |
| 0xF0     | suppressed                  | constant up       |
| 0xFF     | suppressed                  | constant up, fast |

`0xC0` is the **minimum value** that:

- Registers as "non-neutral" to the auto-focus trigger (so on release, the game doesn't snap)
- Stays below the pitch-input scaling curve's take-effect threshold (so no drift)

Anywhere in `[0xC0, 0xDF]` would likely work; `0xC0` chosen as the smallest known-good.

### The deadzone range `[0x41, 0xBF]`

This is the symmetric range around `0x80` with a radius of `0x3F` (63 units). It's slightly larger than the known `0xC0` threshold (60 units above center), giving some margin for sensor drift on real analog sticks. Without that margin, a resting stick that reads `0x7E` or `0x82` (one or two units off exact center) would be treated as "held" and the substitute wouldn't apply — auto-focus would fire.

The check `addiu at, v0, -0x41; sltiu at, at, 0x7F` computes "is `v0` in the half-open interval `[0x41, 0xC0)` = `[0x41, 0xBF]`" in two instructions. It's shorter than an explicit pair of comparisons.

### The trampoline location `0x001A4984`

Chosen from `find_free_space.py`'s output. Criteria:

- Large enough run of zeros (≥ 11 words): `0x001A4984` has 39 zero-words. ✓
- Small enough to clearly be inter-function alignment padding, not an actively-used BSS region (which might get re-zeroed by the game during scene transitions).
- Close to the hook site (for human readability; MIPS `j` reaches anywhere in the 256 MB segment, so distance doesn't matter for correctness).

### The mode flag `0x0106C9FC`

Chosen from the stable-diff candidates because:

- Clean `0 ↔ 1` integer flag (easy to test with `beq zero`)
- Stable over seconds of sampling within a state
- Different value between free-roam and aim
- No observed spurious flips

Other candidates would have worked; this one was arbitrary among the cleanest.

---

## 9. What This Reveals About SotC's Camera

The reverse-engineering process exposed several architectural details:

### Two-stick input pipeline with unified decoding

SotC's input path decodes **all** stick/button bytes through the same pad-read function at `0x001ACD44`. Both left and right sticks, both analog and digital inputs, flow through this one entry point. The function has no knowledge of which camera mode is active — it just writes decoded state into a scratch buffer.

**Implication for patching:** any per-mode customization has to be either (a) detected via memory state (the mode-flag approach) or (b) done downstream of the pad-decode.

### Camera-mode state in a consolidated struct

The memory region `0x0106A000..0x0106E000` is packed with camera-related state. The stable-state diff turned up 646 flags and integers that differ between free-roam and bow-aim. That's far more than necessary just to distinguish "which camera is active" — it suggests the game stores a significant amount of per-mode configuration (field-of-view, pitch limits, sensitivity curves, smoothing rates, aim-assist strength, reticle positions, etc.) that is swapped in/out when modes change.

This is consistent with how modern games handle camera-mode transitions: rather than conditional logic in the camera controller, each mode is a "preset" that replaces the active configuration.

### Free-roam auto-focus is a VU0 computation

We never located a `lerp_rate` constant or a `target_pitch` memory variable that could be hammered to disable auto-focus directly. Full-EE scans for the "neutral pitch" scalar `4.55981` (observed in FPR `$f04`) returned zero hits — no instruction loads it, no memory holds it.

The most plausible explanation: the lerp computation happens entirely in VU0 macro-mode instructions using register-resident constants loaded at VU-code time. The VU program has the "neutral pitch" value baked in, and it computes the new pitch on every frame without ever touching EE main memory.

**Implication:** you cannot disable auto-focus by changing a memory constant. You have to disable its **trigger** — the "stick is released" condition that launches the lerp. That trigger is what our patch attacks.

### Auto-focus uses a fat deadzone

The `[0x41, 0xBF]` range (radius 63) is surprisingly wide — that's about 50% of the stick's travel on each side of center. Most sticks have a hardware deadzone of a few units; this is clearly a _gameplay_ deadzone, deliberately wide so that partial stick movements aren't interpreted as "deliberate pitch hold." The trade-off is that auto-focus fires very eagerly: even a slight stick nudge won't disarm it.

### Pitch input has a separate, smaller threshold

The `[0xE0, 0xFF]` active-pitch range (radius 31) is tighter than the deadzone. This means there's an "in-between" region (`0xC0..0xDF` for up, `0x20..0x3F` for down) where the stick is considered "held" (no auto-focus) but "not held enough to produce motion." The patch lives in exactly that window — it's the only place where a fixed substitute value can defeat auto-focus without producing drift.

This two-threshold system (wide neutral check, narrow active-input check) is a deliberate design: it prevents accidental camera drift from casual stick contact but still triggers auto-focus readily when the player truly releases the stick.

### The live camera controller is at `0x01C18890`, not `0x01C180A0`

The original research identified a camera controller struct at `0x01C180A0`, but its orientation matrix stayed at pure identity during live rotation. The **real** controller is at `0x01C18890`, immediately adjacent. Both are legitimate instances — the decoy at `0x01C180A0` may be for a secondary camera (cutscene, locked-on colossus) that wasn't exercised during testing.

---

## 10. Porting to Other SotC Builds

This patch targets PAL SCES-53326 (CRC `0F0C4A9C`). Porting to other releases (NTSC-U SCUS-97472 = `877F3436`, NTSC-J, HD remasters on PS3/PS4, etc.) requires re-finding:

1. **The pad-read hook site.** Search for a MIPS instruction sequence `lbu rN, offset(rM); sb rN, offset2(rO)` that reads bytes at consecutive offsets into a scratch struct. It's likely in a similarly-named function region.

2. **An available trampoline location.** Run `find_free_space.py` (adjusted for the target region) against the target build.

3. **The auto-focus neutral-deadzone threshold.** Binary-search with a constant-substitute patch, same method as this session (§8). Different builds may have different thresholds.

4. **The pitch-input take-effect threshold.** Same method — find the minimum substitute value that produces drift.

5. **The aim-mode flag.** Run `find_stable_flags.py` (adjust regions for the target). Take snapshots in free-roam idle and bow-aim. The clean 0↔1 flag in the camera config region is likely the equivalent of `0x0106C9FC`.

6. **Re-encode the MIPS instructions** with the new target addresses, branch offsets, and flag address.

The overall technique — hook the pad-read, trampoline with deadzone substitute, mode-flag bypass — should transfer cleanly. Only the specific addresses and encoded words change.

---

## Summary

The patch is 13 single-word writes. Nine of them define a small conditional-substitute routine in unused memory; two redirect the camera's pad-byte read to that routine; the remaining two are the trampoline's branch-offset `nop`s.

It works because:

- SotC's auto-focus trigger is a "neutral deadzone" check on the raw pad byte
- There's a window of values that are "non-neutral for trigger purposes" but "below the pitch-input threshold"
- Substituting the pad byte into that window on release (and only on release) disarms auto-focus without producing drift
- A separately-discovered mode flag lets us bypass the substitute for aim cameras, which interpret the byte differently

It doesn't work by finding and modifying the auto-focus math (that's all VU0, inaccessible from EE). It works by making the pad-read report values that the game's existing auto-focus-trigger logic treats as "stick is held" — even when the player hasn't touched it.

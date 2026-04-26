# Camera velocity-cap pnach — how it works

Applies to: `patches/0F0C4A9C_camera_velocity_cap.pnach`

This pnach is **independent from the aim-tracking variants**. It can be enabled alone, or alongside any other camera-fix component or aim-tracking bundle. No address overlap. No shared state.

---

## The problem

SotC's camera integrates yaw and pitch **angular velocity** over time while the right stick is held. Each axis has an accumulator that stores the current speed in radians per second:

| Field       | Address       | What it is                                  |
| ----------- | ------------- | ------------------------------------------- |
| `yaw_vel`   | `0x0106DEF8`  | Yaw angular velocity, radians/sec, signed   |
| `yaw_dt`    | `0x0106DEFC`  | Per-frame yaw delta (≈ yaw_vel / 60)        |
| `pitch_vel` | `0x0106DF04`  | Pitch angular velocity, radians/sec, signed |
| `pitch_dt`  | `0x0106DF08`  | Per-frame pitch delta (≈ pitch_vel / 60)    |

When you hold the stick, `yaw_vel` and `pitch_vel` **ramp up over ~0.87 seconds** and **saturate** at the game's preset maxima. When you release, they **decay over another ~0.87 seconds** back to 0.

This integration produces three annoyances:

1. **Build-up feel** — the longer you hold, the faster the camera goes, up to the saturation ceiling.
2. **Compound acceleration on repeat presses** — because decay between presses doesn't fully complete, each press starts from a residual velocity rather than zero, so repeated small taps in the same direction reach full speed faster than a single long press.
3. **Drift after release** — the camera coasts for ~0.88 s as velocity decays back to zero.

The problem is most pronounced for yaw, whose vanilla saturation is very high (300°/s).

---

## Vanilla behavior (measured)

Live sampling of `0x0106DEF8` and `0x0106DF04` during a controlled push-and-release test, without any patch:

| Axis    | Vanilla saturation                      | Time to saturate from 0 | Time to decay to 0 | Compound accel?                         |
| ------- | --------------------------------------- | ----------------------- | ------------------ | --------------------------------------- |
| Yaw     | **5.236 rad/s** = 5π/3 ≈ **300°/s**     | ~0.87 s                 | ~0.87 s            | Yes — second press starts at ~0.88 rad/s instead of ~0.51 on first |
| Pitch   | **1.396 rad/s** ≈ **80°/s**             | ~0.87 s                 | ~0.87 s            | Same pattern, less visible due to lower ceiling |

Both saturations come from the same underlying velocity-update function (`0x01358E78`), which is called twice per frame with different arguments — once for the yaw accumulator (`$a0 = 0x0106DEF8`) and once for the pitch accumulator (`$a0 = 0x0106DF04`).

---

## What this pnach changes

**One instruction rewritten + 24 instructions of new trampoline in previously-zero padding.**

### Hook site — single instruction replaced

| Address        | Vanilla    | Patched    | Meaning                                  |
| -------------- | ---------- | ---------- | ---------------------------------------- |
| `0x01359008`   | `0x03E00008` (`jr $ra`) | `0x0804BBF3` (`j 0x0012EFCC`) | Velocity function's final return is redirected to our trampoline |

The delay slot at `0x0135900C` (`addiu $sp, $sp, +96`, restores the stack) is untouched — it still executes before the jump takes effect.

### Trampoline body at `0x0012EFCC`

24 words in 33-word-long code-alignment padding. All were previously `0x00000000` (zero padding between functions).

The trampoline, decoded:

```asm
lui   $at, 0x0107             # at = 0x01070000 (base for both vel addrs)
lwc1  $f3, -0x2108($at)       # f3 = yaw_vel     (0x0106DEF8)
lui   $t0, 0x4000             # t0 = 0x40000000 = bit pattern for 2.0f
mtc1  $t0, $f1                # f1 = 2.0f
neg.s $f2, $f1                # f2 = -2.0f

# --- clamp yaw_vel ---
c.olt.s $f1, $f3              # is 2.0 < yaw_vel?
bc1f  try_yaw_neg             # if not, try the negative side
nop
swc1  $f1, -0x2108($at)       # yaw_vel = 2.0 (clamp high)
try_yaw_neg:
c.olt.s $f3, $f2              # is yaw_vel < -2.0?
bc1f  clamp_pitch             # if not, done with yaw
nop
swc1  $f2, -0x2108($at)       # yaw_vel = -2.0 (clamp low)

# --- clamp pitch_vel (same logic, different address offset) ---
clamp_pitch:
lwc1  $f3, -0x20FC($at)       # f3 = pitch_vel  (0x0106DF04)
c.olt.s $f1, $f3
bc1f  try_pitch_neg
nop
swc1  $f1, -0x20FC($at)       # pitch_vel = 2.0
try_pitch_neg:
c.olt.s $f3, $f2
bc1f  done
nop
swc1  $f2, -0x20FC($at)       # pitch_vel = -2.0

done:
jr    $ra                     # return to the original caller
nop
```

Register usage: `$at`, `$t0`, `$f1`, `$f2`, `$f3`. All caller-save on PS2 EE. We specifically **avoid clobbering `$f0`** because the velocity-update function returns its computed result in `$f0`, which the caller reads immediately after the `jal`. Clobbering `$f0` caused an earlier bug where yaw froze and pitch moved diagonally — the caller was using our trampoline's scratch value as camera state.

---

## Full word-level comparison

Everything the pnach writes, with the vanilla value at each address.

### Hook (1 word)

| Address    | Vanilla    | Patched    |
| ---------- | ---------- | ---------- |
| `0x01359008` | `0x03E00008` | `0x0804BBF3` |

### Trampoline body (24 words, all previously zero)

| Address        | Vanilla    | Patched    | Instruction                          |
| -------------- | ---------- | ---------- | ------------------------------------ |
| `0x0012EFCC`   | `0x00000000` | `0x3C010107` | `lui $at, 0x0107`                    |
| `0x0012EFD0`   | `0x00000000` | `0xC423DEF8` | `lwc1 $f3, -0x2108($at)`             |
| `0x0012EFD4`   | `0x00000000` | `0x3C084000` | `lui $t0, 0x4000`                    |
| `0x0012EFD8`   | `0x00000000` | `0x44880800` | `mtc1 $t0, $f1`                      |
| `0x0012EFDC`   | `0x00000000` | `0x46000887` | `neg.s $f2, $f1`                     |
| `0x0012EFE0`   | `0x00000000` | `0x46030834` | `c.olt.s $f1, $f3`                   |
| `0x0012EFE4`   | `0x00000000` | `0x45000002` | `bc1f +2`                            |
| `0x0012EFE8`   | `0x00000000` | `0x00000000` | `nop`                                |
| `0x0012EFEC`   | `0x00000000` | `0xE421DEF8` | `swc1 $f1, -0x2108($at)` (yaw = +2)  |
| `0x0012EFF0`   | `0x00000000` | `0x46021834` | `c.olt.s $f3, $f2`                   |
| `0x0012EFF4`   | `0x00000000` | `0x45000002` | `bc1f +2`                            |
| `0x0012EFF8`   | `0x00000000` | `0x00000000` | `nop`                                |
| `0x0012EFFC`   | `0x00000000` | `0xE422DEF8` | `swc1 $f2, -0x2108($at)` (yaw = -2)  |
| `0x0012F000`   | `0x00000000` | `0xC423DF04` | `lwc1 $f3, -0x20FC($at)`             |
| `0x0012F004`   | `0x00000000` | `0x46030834` | `c.olt.s $f1, $f3`                   |
| `0x0012F008`   | `0x00000000` | `0x45000002` | `bc1f +2`                            |
| `0x0012F00C`   | `0x00000000` | `0x00000000` | `nop`                                |
| `0x0012F010`   | `0x00000000` | `0xE421DF04` | `swc1 $f1, -0x20FC($at)` (pitch=+2)  |
| `0x0012F014`   | `0x00000000` | `0x46021834` | `c.olt.s $f3, $f2`                   |
| `0x0012F018`   | `0x00000000` | `0x45000002` | `bc1f +2`                            |
| `0x0012F01C`   | `0x00000000` | `0x00000000` | `nop`                                |
| `0x0012F020`   | `0x00000000` | `0xE422DF04` | `swc1 $f2, -0x20FC($at)` (pitch=-2)  |
| `0x0012F024`   | `0x00000000` | `0x03E00008` | `jr $ra` (return to caller)          |
| `0x0012F028`   | `0x00000000` | `0x00000000` | `nop`                                |

---

## Effective runtime behavior

| Metric                              | Vanilla              | Patched              | Delta                              |
| ----------------------------------- | -------------------- | -------------------- | ---------------------------------- |
| Yaw max speed                       | 5.236 rad/s (300°/s) | 2.000 rad/s (115°/s) | **–62 % max**                      |
| Pitch max speed                     | 1.396 rad/s (80°/s)  | unchanged            | 0 (natural max is below cap)       |
| Time to reach max (from 0)          | ~0.87 s              | ~0.33 s              | Faster, but **to a lower max**     |
| Time to decay to 0 (from max)       | ~0.87 s              | ~0.33 s              | Faster, but from a lower peak      |
| Game-code growth rate per frame     | unchanged            | unchanged            | —                                  |
| Game-code decay rate per frame      | unchanged            | unchanged            | —                                  |
| Compound accel on repeat presses    | still present        | present but **capped at 2.0** | Much less visible                  |

---

## What this pnach does NOT do

- Does **not** change the game's per-frame growth increment — ramps still accelerate at the game's natural rate, they just hit a lower ceiling.
- Does **not** add snap-to-zero on stick release — the camera still coasts (decays) after release, just over a shorter range.
- Does **not** touch pitch in a meaningful way — pitch's natural 1.4 rad/s max is already below our 2.0 cap.

If you want finer control over these behaviors — growth dampening, aggressive snap-on-release, independent yaw/pitch caps — use the live tuning tool `tools/cap_camera_velocity.py`. It hammers the same two accumulators via PINE at ~125 Hz and supports per-axis settings and three presets (`v1`, `v2`, `v3`). That tool is the reference for what a future v2 of this pnach might bake in.

---

## Why the addresses don't conflict with the aim-tracking variants

| Pnach                            | Hook sites                        | Trampoline body                     |
| -------------------------------- | --------------------------------- | ----------------------------------- |
| `aim_tracks_camera_*_stick`      | `0x001ACD44`, `0x01176AB4`        | `0x001A4984..0x001A4A04`            |
| `camera_velocity_cap`            | `0x01359008`                      | `0x0012EFCC..0x0012F028`            |

Completely disjoint. PCSX2 loads both pnach files if both are in the patches folder, and their per-vsync writes don't race each other.

---

## Finding the pieces — brief RE notes

- **Velocity accumulator addresses** (`0x0106DEF8`, `0x0106DF04`) were found by sampling a 256-byte window around the camera yaw state (`0x0106DF00`) during a controlled push-and-release test, looking for floats that ramp up and decay back to 0. Yaw matched instantly; pitch was derived from the caller structure (the velocity function takes `$a0` = pointer to the accumulator, and the two callers pass `s0+84` and `s0+96` respectively with `s0 = 0x0106DEA4`).
- **Velocity-update function** (`0x01358E78`) was found by setting a PCSX2 write-breakpoint on `0x0106DEF8` and reading back PC.
- **Saturation constants** (5.236, 1.4) are **not code immediates** — they're loaded from a game data struct via `lwc1 $f18, 12($s1)` and `lwc1 $f18, 28($s1)` in the callers at `0x01357800` and `0x0135794C`. That's why a simpler "change one `lui`" patch wasn't possible; the fix had to clamp the _output_ in a trampoline.
- **Hook site choice** (`0x01359008 = jr $ra`) was picked because it's the unique exit of the velocity function, runs once per call regardless of which internal branch was taken, and has a clean delay slot (`addiu $sp, $sp, +96`) we could leave in place.
- **Padding for the trampoline** (`0x0012EFCC`, 33 free words) was found with `tools/find_free_space.py`. Any of several similar inter-function padding regions would have worked; `0x0012E???` was chosen for being far from v18's padding to guarantee no conflict.

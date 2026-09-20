# Smash 64 for New Nintendo 3DS

A native port of **Super Smash Bros. for Nintendo 64** to homebrewed New Nintendo 3DS systems, built from the game's decompilation. The original game runs on the ARM11 CPU and renders through the PICA200 GPU, with stereoscopic 3D controlled by the console's 3D slider.

## Features

- Original single-player modes and Versus against CPU opponents.
- Full-height 4:3 gameplay, with optional widescreen that expands the camera view without stretching fighters.
- A bottom-screen HUD with character portraits, damage, stocks or scores, and a true-combo counter.
- Touch controls for display settings, FPS information, and control options.
- Optional **tap jump off** and **C-stick smash attacks / directional aerials**. X/Y jumping remains available.
- Saved preferences, native audio, and bounded performance reports for troubleshooting.

This port targets **New Nintendo 3DS and New Nintendo 3DS XL**. Original 3DS/2DS models are not supported. Local and wireless multiplayer are not implemented. Performance is optimized for the New 3DS; a locked 60 FPS is not guaranteed in every situation.

## Installation

This is a **source release**. You need your own **US 1.0 `.z64` ROM** to build an installable CIA; no ROM, extracted game assets, save files, or prebuilt game binaries are distributed here. See the [build guide](docs/BUILD-3DS.md).

1. Build `Smash64-New3DS.cia` using the guide.
2. Copy it to the SD card in your homebrewed New 3DS.
3. Open **FBI**, select the CIA, and choose **Install CIA**.
4. Launch **Smash 64** from the HOME Menu and adjust the 3D slider to taste.

For audio, `/3ds/dspfirm.cdc` must be present. Current Luma3DS provides a DSP firmware dump in **Rosalina → Miscellaneous options**. Use the firmware from your own console.

Updates use the same title ID and preserve `/3ds/ssb64/save.bin`. Back up this folder before updating. An optional N64 `.srm` save can be imported when building; otherwise the game starts with a fresh save.

## Controls

| Input | Action |
|---|---|
| Circle Pad | Move; tap up to jump when enabled |
| A / B | Attack / special |
| X or Y | Jump |
| L or R | Shield |
| ZL or ZR | Grab |
| D-pad Up | Taunt |
| Start | Pause |
| Select | Save performance reports and exit |
| C-stick, when enabled | Smash attack on the ground; directional aerial in the air |

Tap **CONTROLS** on the bottom screen to switch **TAP JUMP** between ON/OFF or **C-STICK** between OFF/SMASH. Defaults preserve the original controls: tap jump on, C-stick off. Return the nub to center between attacks. Options save automatically and apply to the built-in player controls.

Tap **VIEW** for 4:3/widescreen and **FPS** for performance details. Reports rotate through eight match files in `/3ds/ssb64/perf/`; they do not accumulate per-frame logs indefinitely.

## Building and contributing

The [Windows build guide](docs/BUILD-3DS.md) covers the toolchain and ROM requirements. The `3ds/` directory contains the platform code and build tools; the root `src/` directory contains the game code. Dependencies are pinned as Git submodules. Please do not submit ROMs, extracted assets, saves, firmware, or compiled game packages in issues or pull requests.

Bug reports are most useful with the console model, stage, fighters, display mode, 3D slider setting, and relevant performance report. Emulator results help reproduce bugs but do not establish console performance.

## Credits

- [ssb-decomp-re](https://github.com/VetriTheRetri/ssb-decomp-re) and its contributors for the original decompilation.
- [JRickey's BattleShip](https://github.com/JRickey/BattleShip) and its port-patches branch for the native engine, asset, and audio work this port builds on.
- [SM64 3DS graphics backend](https://github.com/mkst/sm64-port/tree/3ds-port), devkitPro, libctru, citro3d, and the 3DS homebrew community.

Component licenses and notices are retained in [3ds/licenses](3ds/licenses) and the upstream sources. The graphics backend permits source distribution, not binary redistribution; this repository therefore publishes source only. Original game and HOME Menu artwork belong to Nintendo / HAL Laboratory. This is an unofficial fan project, not affiliated with or endorsed by Nintendo.

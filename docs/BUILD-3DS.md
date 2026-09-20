# Build an installable CIA on Windows

## Requirements

- Windows, Git, and Python 3.10 or newer.
- A devkitPro installation containing devkitARM, libctru, citro3d, and the 3DS tools. The tested C/C++ runtime is GCC **16.1.0**.
- LLVM/Clang with `clang.exe`, `clang++.exe`, `ld.lld.exe`, `llvm-ar.exe`, and `llvm-nm.exe`. The tested compiler is LLVM-MinGW 20260908 UCRT x86_64; the game itself targets `arm-none-eabi` and uses the devkitARM runtime.
- `picasso.exe`, `3dsxtool.exe`, `bannertool.exe`, and `makerom.exe`.
- Your own unmodified **Super Smash Bros. (USA), revision 1.0**, in big-endian `.z64` format: 16,777,216 bytes, SHA-1 `e2929e10fccc0aa84e5776227e798abc07cedabf`.

Obtain the tools from [devkitPro](https://devkitpro.org/), [LLVM-MinGW](https://github.com/mstorsjo/llvm-mingw/releases), [bannertool](https://github.com/Steveice10/bannertool), and [Project CTR](https://github.com/3DSGuy/Project_CTR). Keep a full devkitARM installation, including its C++ headers. This repository does not install or download a toolchain automatically.

## Clone and configure

Use a Git clone rather than GitHub's source ZIP, which does not include submodules:

```powershell
git clone --branch 3ds https://github.com/2gifts/smash64-3ds.git
cd smash64-3ds
git submodule update --init 3ds/vendor/BattleShip 3ds/vendor/sm64-3ds
git -C 3ds/vendor/BattleShip submodule update --init decomp libultraship
cd 3ds
python -m pip install -r requirements.txt
Copy-Item build-config.example.json build-config.json
```

Edit `build-config.json` to point to your installed tools. Use forward slashes in JSON paths. Set `gcc_version` to the installed runtime version; 16.1.0 is the validated version. If C++ headers are stored separately, add `cxx_include` pointing to the version directory containing `vector` and the `arm-none-eabi` directory.

The two top-level submodules and BattleShip's nested dependencies are pinned to tested commits. The root game source is compiled for this port; BattleShip's nested decomp checkout supplies upstream generation inputs. Torch and desktop GUI dependencies are not needed.

## Build

Run from `3ds/`:

```powershell
python tools/build_release.py --rom "C:/Games/SSB64/baserom.us.z64"
```

To import your own completed N64 save, add `--save "C:/Games/SSB64/Smash64.srm"`. The original ROM and save are read only. Without an imported save, the build contains a fresh save. An existing save on the console always takes priority.

The script checks the ROM, extracts assets locally, compiles the game and renderer, downloads the credited HOME Menu artwork, and verifies the CIA's executable and asset contents. Build output is:

```text
3ds/build/release/Smash64-New3DS.cia
```

Copy that file to your SD card and install it with FBI. The application title ID is `000400000FF64000`. Its settings, save, and bounded performance logs live under `/3ds/ssb64/` on the SD card. DSP firmware from your console is required for audio.

Build output, extracted assets, personal configuration, and downloaded artwork are ignored by Git. Do not distribute the resulting game package; this project and its graphics dependency are released in source form.

## Developer checks

After extracting assets, the Windows host compiler can exercise the settings and bottom-screen UI:

```powershell
python tools/controls_test.py
python tools/bottom_host_test.py
python tools/display_test.py
python tools/performance_test.py
python tools/io_host_test.py
python tools/assets_cache_test.py
python tools/bottom_state_test.py
```

Release validation also includes emulator checks of touch persistence, actual smash/aerial action states, tap-jump behavior, held-nub behavior, and an installed match through results. New 3DS hardware testing is still necessary for input feel and performance; emulator timing is not a hardware benchmark.

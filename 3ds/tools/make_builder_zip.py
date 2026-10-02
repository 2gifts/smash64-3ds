"""Make the one-click builder download for a GitHub release.

  python tools/make_builder_zip.py 1.1.0 [--allow-dirty]

The zip holds source only: this repository's tracked files plus the pinned
submodule sources the build reads (the graphics backend's license permits
source, not binary, redistribution). The user's ROM supplies the game.

  Smash 64 CIA Builder/Build Smash 64 CIA.bat   (3ds/tools/easy_build/)
  Smash 64 CIA Builder/READ ME FIRST.txt
  Smash 64 CIA Builder/builder/...              (repository layout, BUILDER_VERSION)
"""
import argparse
import subprocess
import time
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
TOP = 'Smash 64 CIA Builder'
# Never ship game data or built executables, whatever is tracked.
FORBIDDEN = {'.z64', '.n64', '.v64', '.rom', '.srm', '.eep', '.cia', '.3dsx', '.elf', '.cxi', '.o', '.a',
             '.cdc', '.bnr', '.wav', '.o2r', '.otr'}
WINDOWS_TEXT = {'.bat', '.ps1', '.txt'}
# Submodule sources, by the paths the build reads. Each prefix is relative to
# the submodule; None keeps every tracked file.
SUBMODULES = {
    '3ds/vendor/BattleShip': None,
    '3ds/vendor/BattleShip/decomp': None,
    # Headers only (the port compiles none of its desktop sources).
    '3ds/vendor/BattleShip/libultraship': ('LICENSE', 'README.md', 'include/', 'src/ship/events/'),
    # The adapted renderer copies these files (tools/prepare_render.py).
    '3ds/vendor/sm64-3ds': ('README.md', 'src/pc/gfx/gfx_', 'src/pc/gfx/shader', 'src/pc/gfx/LICENSE.txt',
                            'src/pc/gfx/README.md', 'src/pc/gfx/color_conversion.h'),
}
# Repository files the build never reads (README media, desktop tooling).
SKIP = ('docs/media/',)


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def tracked(path):
    """Tracked regular files of one repository, excluding its submodule links."""
    links = {line.split()[3] for line in git(path, 'ls-files', '-s').splitlines() if line.startswith('160000')}
    return [n for n in git(path, 'ls-files', '-z').split('\0') if n and n not in links]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('version')
    ap.add_argument('--allow-dirty', action='store_true', help='Include uncommitted changes (testing only)')
    args = ap.parse_args()
    if not args.allow_dirty and git(REPO, 'status', '--porcelain', '--untracked-files=no').strip():
        raise SystemExit('The repository has uncommitted changes; commit them or pass --allow-dirty')
    files = {}
    for name in tracked(REPO):
        if not name.startswith(SKIP):
            files[name] = REPO/name
    for sub, keep in SUBMODULES.items():
        root = REPO/sub
        if not (root/'.git').exists():
            raise SystemExit(f'{sub} is not checked out; run git submodule update --init --recursive')
        for name in tracked(root):
            if keep is None or name.startswith(keep):
                files[f'{sub}/{name}'] = root/name
    files = {k: v for k, v in files.items() if v.is_file()}
    bad = [n for n in files if PurePosixPath(n).suffix.lower() in FORBIDDEN]
    if bad:
        raise SystemExit(f'Refusing to package game or build files: {bad[:5]}')
    longest = max(len(f'{TOP}/builder/{n}') for n in files)
    if longest > 180:
        raise SystemExit(f'A packaged path is {longest} characters; Windows Explorer may fail to extract it')
    stamp = time.localtime(int(git(REPO, 'log', '-1', '--format=%ct').strip()))[:6]
    out = REPO/f'3ds/dist/Smash64-3DS-CIA-Builder-v{args.version}.zip'
    out.parent.mkdir(parents=True, exist_ok=True)

    def add(z, arcname, data):
        info = zipfile.ZipInfo(f'{TOP}/{arcname}', stamp)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        # Only the builder's own Windows files; game sources keep their bytes.
        ours = '/' not in arcname or arcname.startswith('builder/3ds/tools/easy_build/')
        if ours and PurePosixPath(arcname).suffix.lower() in WINDOWS_TEXT:
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        z.writestr(info, data)

    with zipfile.ZipFile(out, 'w', compresslevel=9) as z:
        easy = REPO/'3ds/tools/easy_build'
        add(z, 'Build Smash 64 CIA.bat', (easy/'Build Smash 64 CIA.bat').read_bytes())
        add(z, 'READ ME FIRST.txt', (easy/'READ ME FIRST.txt').read_bytes())
        for name in sorted(files):
            add(z, f'builder/{name}', files[name].read_bytes())
        add(z, 'builder/BUILDER_VERSION', f'{args.version}\n'.encode())
    print(f'{out} ({out.stat().st_size/1e6:.1f} MB, {len(files)} source files, longest path {longest})')


if __name__ == '__main__':
    main()

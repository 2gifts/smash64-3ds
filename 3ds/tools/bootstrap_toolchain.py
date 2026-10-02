"""Set up the tested portable Windows toolchain inside 3ds/toolchain/.

Downloads are pinned and hash-checked: LLVM-MinGW, the ARM headers and
libraries from the official devkitPro devkitARM container image, makerom and
bannertool. picasso and 3dsxtool are compiled from pinned devkitPro sources.
Linux executables in the container layer are skipped. Nothing is installed
outside this folder, and build-config.json is written to point at it.

  python tools/bootstrap_toolchain.py
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT/'toolchain'
DOWNLOADS = LOCAL/'downloads'
LOCK = json.loads((ROOT/'toolchain.lock.json').read_text())


def say(text):
    print(text, flush=True)


def run(*args, cwd=None):
    subprocess.run(list(map(str, args)), cwd=cwd or ROOT, check=True)


def sha256_file(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def download(url, dest, digest, headers=None):
    if dest.exists() and sha256_file(dest) == digest:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix+'.partial')
    request = urllib.request.Request(url, headers={'User-Agent': 'smash64-3ds-builder', **(headers or {})})
    with urllib.request.urlopen(request, timeout=120) as src, partial.open('wb') as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    if sha256_file(partial) != digest:
        partial.unlink()
        raise RuntimeError(f'Download checksum mismatch: {dest.name}')
    partial.replace(dest)
    return dest


def safe_extract_zip(archive, dest, strip_root=False):
    dest = dest.resolve()
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            parts = Path(entry.filename).parts[1 if strip_root else 0:]
            if not parts or entry.is_dir():
                continue
            target = dest.joinpath(*parts).resolve()
            if not target.is_relative_to(dest):
                raise RuntimeError(f'Unsafe path in {archive.name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(entry))


def checkout(url, commit, path):
    if (path/'.git').exists():
        rev = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if rev == commit:
            return
        shutil.rmtree(path, onexc=lambda f, p, _: (os.chmod(p, 0o700), f(p)))
    run('git', 'clone', '--no-checkout', '--filter=blob:none', url, path)
    run('git', '-C', path, 'checkout', '--detach', commit)


def llvm():
    bin_dir = LOCAL/LOCK['llvm_directory']/'bin'
    if not (bin_dir/'clang.exe').exists():
        say('LLVM-MinGW (about 160 MB)')
        archive = download(LOCK['llvm_url'], DOWNLOADS/'llvm-mingw.zip', LOCK['llvm_sha256'])
        safe_extract_zip(archive, LOCAL)
    return bin_dir


def sdk():
    root = LOCAL/'devkitpro'
    if (root/'libctru/lib/libctru.a').exists() and (root/'libctru/lib/libcitro3d.a').exists():
        return root
    say('devkitARM, libctru and citro3d from the official devkitPro image (about 250 MB)')
    layer = DOWNLOADS/'devkitarm-layer.tar.gz'
    digest = LOCK['sdk_layer'].split(':')[1]
    if not layer.exists() or sha256_file(layer) != digest:
        token_url = ('https://auth.docker.io/token?service=registry.docker.io'
                     '&scope=repository:devkitpro/devkitarm:pull')
        with urllib.request.urlopen(token_url, timeout=30) as response:
            token = json.load(response)['token']
        download('https://registry-1.docker.io/v2/devkitpro/devkitarm/blobs/'+LOCK['sdk_layer'],
                 layer, digest, {'Authorization': 'Bearer '+token})
    out = root.resolve()
    count = 0
    with tarfile.open(layer, 'r:gz') as tar:
        for member in tar:
            p = PurePosixPath(member.name)
            if not member.isfile() or p.parts[:2] != ('opt', 'devkitpro'):
                continue
            rel = Path(*p.parts[2:])
            # Headers (including extensionless C++ ones), libraries and link inputs only.
            in_cxx = 'c++' in rel.parts and 'include' in rel.parts
            if not (rel.suffix in ('.h', '.hpp', '.tcc', '.a', '.o', '.ld', '.specs', '.x')
                    or in_cxx or rel.name in ('3ds_rules', 'base_rules')):
                continue
            target = (out/rel).resolve()
            if not target.is_relative_to(out):
                raise RuntimeError('Archive path escapes SDK directory')
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    say(f'  {count} SDK files')
    return root


def host_tools(bin_dir):
    out = LOCAL/'bin'
    out.mkdir(parents=True, exist_ok=True)
    clangxx = bin_dir/'clang++.exe'
    if not (out/'3dsxtool.exe').exists():
        src = LOCAL/'src/3dstools'
        checkout(LOCK['3dstools_repository'], LOCK['3dstools_commit'], src)
        run(clangxx, '-O2', '-static', src/'src/3dsxtool.cpp', src/'src/romfs.cpp', '-o', out/'3dsxtool.exe')
    if not (out/'picasso.exe').exists():
        src = LOCAL/'src/picasso'
        checkout(LOCK['picasso_repository'], LOCK['picasso_commit'], src)
        run(clangxx, '-O2', '-static', '-DPACKAGE_STRING="picasso '+LOCK['picasso_commit'][:8]+'"',
            src/'source/picasso_assembler.cpp', src/'source/picasso_frontend.cpp', '-o', out/'picasso.exe')
    for name, url, digest in LOCK['cia_tools']:
        exe = out/(name+'.exe')
        if exe.exists():
            continue
        archive = download(url, DOWNLOADS/(name+'.zip'), digest)
        with zipfile.ZipFile(archive) as z:
            found = [e for e in z.infolist() if PurePosixPath(e.filename).name.lower() == name+'.exe'
                     and ('win' in e.filename.lower() or 'windows' in e.filename.lower() or '/' not in e.filename)]
            if not found:
                found = [e for e in z.infolist() if PurePosixPath(e.filename).name.lower() == name+'.exe']
            if not found:
                raise RuntimeError(f'{name}.exe not found in {archive.name}')
            exe.write_bytes(z.read(found[0]))
    return out


def main():
    if os.name != 'nt':
        sys.exit('This sets up the Windows toolchain. On Linux/macOS, install devkitPro 3ds-dev and LLVM.')
    bin_dir = llvm()
    root = sdk()
    tools = host_tools(bin_dir)
    versions = sorted((root/'devkitARM/lib/gcc/arm-none-eabi').iterdir())
    gcc = versions[-1].name
    config_path = ROOT/'build-config.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config.update({'devkitpro': root.resolve().as_posix(), 'llvm_bin': bin_dir.resolve().as_posix(),
                   'gcc_version': gcc,
                   **{name: (tools/(name+'.exe')).resolve().as_posix()
                      for name in ('picasso', '3dsxtool', 'bannertool', 'makerom')}})
    config_path.write_text(json.dumps(config, indent=2)+'\n')
    say(f'Toolchain ready (devkitARM GCC {gcc}). Wrote {config_path.name}.')


if __name__ == '__main__':
    main()

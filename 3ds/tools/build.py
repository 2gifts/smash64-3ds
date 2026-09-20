"""Cross-compile the original Smash 64 game to ARM11 using the pinned port source.

Paths are configurable through the ignored build-config.json file.
"""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'build-config.json').read_text()) if (ROOT/'build-config.json').exists() else {}
def configured(name,default):return Path(CONFIG.get(name,default)).expanduser().resolve()
UPSTREAM = configured('battleship',ROOT/'vendor/BattleShip' if (ROOT/'vendor/BattleShip').exists() else ROOT.parent/'BattleShip')
DECOMP = configured('decomp',ROOT.parent if (ROOT.parent/'src/ft').exists() else UPSTREAM/'decomp')
RENDER_SOURCE = configured('renderer',ROOT/'vendor/sm64-3ds' if (ROOT/'vendor/sm64-3ds').exists() else ROOT.parent/'sm64-3ds')
SDK = configured('devkitpro',os.environ.get('DEVKITPRO','C:/devkitPro'))
ARM = SDK / 'devkitARM'
BIN = configured('llvm_bin',os.environ.get('LLVM_BIN','C:/Program Files/LLVM/bin'))
MELEE = configured('legacy_workspace',ROOT/'emulator-tools')
GCC_VERSION = CONFIG.get('gcc_version','16.1.0')
def tool(name):
    if name in CONFIG:return str(configured(name,CONFIG[name]))
    bundled=SDK/'tools/bin'/(name+'.exe')
    return str(bundled) if bundled.exists() else name+'.exe'
OUT = Path(os.environ.get('SSB_BUILD_DIR',ROOT/'build')).resolve()
(OUT/'tmp').mkdir(parents=True,exist_ok=True)
os.environ['TMP']=os.environ['TEMP']=str(OUT/'tmp')
ARCH = ['--no-default-config', '--target=arm-none-eabi', '-mcpu=mpcore',
        '-mfpu=vfp', '-mfloat-abi=hard', '-mtp=soft']

def run(argv, **kw):
    return subprocess.run(list(map(str, argv)), check=True, **kw)

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    run([sys.executable, UPSTREAM / 'tools/generate_reloc_stubs.py'])
    for name, flags in [('staff', []), ('titles', []),
                        ('info', ['-paragraphFont', '-multiline']),
                        ('companies', ['-paragraphFont'])]:
        run([sys.executable, UPSTREAM/'tools/creditsTextConverter.py',
             *flags, name+'.credits.us.txt'], cwd=DECOMP/'src/credits', capture_output=True)

def sources():
    dirs = 'credits ef ft gm gr if it lb mn mp mv sc sys wp'.split()
    files = [p for d in dirs for p in (DECOMP / 'src' / d).rglob('*.c')
             if not p.name.endswith('.inc.c')]
    files += list((UPSTREAM / 'port/stubs').glob('*.c'))
    files += [DECOMP / 'src/libultra/gu' / (n + '.c')
              for n in ['mtxcatf', 'mtxutil', 'mtxxfmf', 'normalize', 'sinf', 'cosf']]
    files += list((DECOMP / 'src/libultra/n_audio').glob('*.c'))
    files += [DECOMP / 'src/libultra/audio/cents2ratio.c']
    return sorted(set(files))

def game_flags():
    includes = [ROOT/'compat', ROOT/'include', UPSTREAM/'include', DECOMP/'include', DECOMP/'src',
                UPSTREAM/'port', UPSTREAM/'debug_tools',
                UPSTREAM/'libultraship/src', UPSTREAM/'libultraship/include']
    includes += [SDK/'libctru/include']
    return [*ARCH, '-std=gnu11', '-O2', '-g', '-fno-short-enums',
            '-fno-strict-aliasing', '-fwrapv', '-ffp-contract=off',
            '-fno-builtin-sinf', '-fno-builtin-cosf',
            '-ffunction-sections', '-fdata-sections',
            '-DREGION_US=1', '-DVERSION_US=1', '-DNON_MATCHING=1',
            '-DNON_EQUIVALENT=1', '-DAVOID_UB=1', '-DPORT=1',
            '-DF3DEX_GBI_2=1', '-D_LANGUAGE_C', '-DN_MICRO=1',
            '-D__3DS__', '-D_USE_MATH_DEFINES',
            '-DosGetTime=ssb_osGetTime',
            '-D__assert=ssb_assert',
            '-Wno-unknown-pragmas', '-Wno-implicit-int', '-Wno-shift-negative-value',
            '-Wno-parentheses-equality', '-Wno-pointer-sign',
            '-Wno-constant-conversion', '-Wno-tautological-constant-out-of-range-compare',
            *['-I'+str(p) for p in includes], '-isystem', str(ARM/'arm-none-eabi/include')]

def compile_game():
    OUT.mkdir(parents=True, exist_ok=True)
    flags = game_flags()
    # Flag changes invalidate all objects; compiler dependency files handle headers.
    stamp_hash = hashlib.sha256('\0'.join(flags).encode())
    for folder in [ROOT/'compat', ROOT/'include', DECOMP/'include', DECOMP/'src', UPSTREAM/'include', UPSTREAM/'port']:
        for h in sorted(folder.rglob('*.h')):
            stamp_hash.update(str(h).encode())
            stamp_hash.update(h.read_bytes())
    stamp = stamp_hash.hexdigest()
    stampfile = OUT/'game-flags.sha256'
    flags_changed = not stampfile.exists() or stampfile.read_text() != stamp
    def one(src):
        rel = Path('decomp')/src.relative_to(DECOMP) if src.is_relative_to(DECOMP) else src.relative_to(UPSTREAM)
        obj = (OUT/'objects'/rel).with_suffix('.o')
        dep = obj.with_suffix('.d')
        cmd = [BIN/'clang.exe', *flags, '-MMD', '-MF', dep, '-c', src, '-o', obj]
        # During bring-up an explicit --all refreshes all dependency state.
        if not flags_changed and '--all' not in sys.argv and obj.exists() and obj.stat().st_mtime > src.stat().st_mtime:
            return str(rel), obj, 0, '', True
        obj.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
        if result.returncode and obj.exists():
            obj.unlink()
        return str(rel), obj, result.returncode, result.stdout + result.stderr, False
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        for i, result in enumerate(pool.map(one, sources()), 1):
            results.append(result)
            if i % 100 == 0:
                print(f'Compiled {i}/{len(sources())}', flush=True)
    failures=[{'file':r[0], 'diagnostic':r[3]} for r in results if r[2]]
    (OUT/'compile-errors.json').write_text(json.dumps(failures, indent=2))
    (OUT/'compile.log').write_text('\n'.join(r[0]+'\n'+r[3] for r in results if r[3]))
    report={'sources':len(results), 'successful':len(results)-len(failures),
            'failures':len(failures), 'cached':sum(r[4] for r in results)}
    (OUT/'compile-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    stampfile.write_text(stamp)
    if failures:
        for f in failures[:5]:
            print(f['file']+'\n'+f['diagnostic'][:1800])
        return 1
    archive=OUT/'libssb64-game.a'
    response=OUT/'archive.rsp'
    response.write_text('\n'.join('"'+str(r[1]).replace('\\','/')+'"' for r in results))
    run([BIN/'llvm-ar.exe','rcs',archive,'@'+str(response)])
    return 0

if __name__ == '__main__':
    if '--prepare' in sys.argv:
        prepare()
    sys.exit(compile_game())

"""Compile the ARM asset, audio and vanilla fighter support libraries."""
import concurrent.futures
import json
import subprocess
import sys
from build import ROOT, UPSTREAM, ARM, SDK, BIN, OUT, ARCH, run, game_flags, GCC_VERSION, configured
from prepare_support import bridges

def compile_support():
    bridges()
    cpp=[*sorted((ROOT/'generated').glob('*.cpp')),
         ROOT/'src/native_assets.cpp',
         UPSTREAM/'port/bridge/lbreloc_byteswap.cpp',
         UPSTREAM/'port/resource/RelocPointerTable.cpp',
         UPSTREAM/'port/resource/RelocFileTable.us.cpp',
         UPSTREAM/'port/port_aobj_fixup.cpp',
         UPSTREAM/'port/fighter_registry.cpp']
    c=[UPSTREAM/'port/audio/mixer.c',UPSTREAM/'port/audio/audio_dma.c']
    cxxver=GCC_VERSION
    cxx=configured('cxx_include',ROOT/'toolchain/c++'/cxxver if (ROOT/'toolchain/c++'/cxxver).exists() else ARM/'arm-none-eabi/include/c++'/cxxver)
    common=[*ARCH,'-O2','-g','-fno-strict-aliasing','-fwrapv','-ffp-contract=off',
            '-ffunction-sections','-fdata-sections','-DREGION_US=1','-DVERSION_US=1','-DPORT=1',
            '-D__3DS__','-fno-short-enums',
            *['-I'+str(p) for p in [ROOT/'include',UPSTREAM/'port',UPSTREAM/'debug_tools',
               UPSTREAM/'libultraship/include',SDK/'libctru/include']]]
    def one(src):
        iscpp=src.suffix=='.cpp'
        obj=OUT/'support'/(src.stem+'.o')
        obj.parent.mkdir(parents=True,exist_ok=True)
        flags=common+(['-std=c++17','-fno-exceptions','-fno-rtti','-nostdinc++',
                       '-isystem',str(cxx),'-isystem',str(cxx/'arm-none-eabi/armv6k/fpu'),
                       '-isystem',str(cxx/'backward')] if iscpp else ['-std=gnu11','-DN_MICRO=1'])
        flags += ['-isystem',str(ARM/'arm-none-eabi/include')]
        cmd=[BIN/('clang++.exe' if iscpp else 'clang.exe'),*flags,'-c',src,'-o',obj]
        p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
        return {'file':str(src),'object':str(obj),'returncode':p.returncode,'diagnostic':p.stdout+p.stderr}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(one,cpp+c))
    (OUT/'support-compile.json').write_text(json.dumps(results,indent=2))
    failures=[r for r in results if r['returncode']]
    print(f'Support: {len(results)-len(failures)}/{len(results)} compiled')
    for f in failures:
        print(f['file']+'\n'+f['diagnostic'][:2500])
    if failures:return 1
    rsp=OUT/'support-archive.rsp'
    rsp.write_text('\n'.join('"'+r['object'].replace('\\','/')+'"' for r in results))
    run([BIN/'llvm-ar.exe','rcs',OUT/'libssb64-support.a','@'+str(rsp)])
    return 0

if __name__=='__main__':
    sys.exit(compile_support())

"""Link an explicitly labelled diagnostic 3DSX for engine bring-up in Azahar."""
from pathlib import Path
import subprocess
import sys
import shutil
import struct
import argparse
from build import ROOT,UPSTREAM,ARM,SDK,BIN,OUT,ARCH,GCC_VERSION,tool,run,game_flags

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--render',action='store_true');ap.add_argument('--release',action='store_true');args=ap.parse_args()
    if args.release:args.render=True
    from prepare_bottom_assets import main as prepare_bottom
    prepare_bottom()
    from prepare_reloc_index import main as prepare_index
    prepare_index()
    variant='release' if args.release else 'graphics' if args.render else 'bringup'
    out=OUT/variant;out.mkdir(parents=True,exist_ok=True)
    objects=[]
    sources=[ROOT/'src/game_host.c',ROOT/'src/vanilla_policy.c',ROOT/'src/coroutine.c',ROOT/'src/platform_3ds.c',ROOT/'src/performance.c',ROOT/'src/save_layout_check.c',ROOT/'src/stereo_camera.c']
    sources += [ROOT/'src/display_settings.c',ROOT/'src/io_worker.c']
    sources += [ROOT/'src/control_settings.c',ROOT/'src/control_input.c',ROOT/'src/control_game.c']
    sources += [ROOT/'src/bottom_game.c',ROOT/'src/bottom_draw.c',ROOT/'src/bottom_3ds.c',ROOT/'src/wallpaper.c']
    if args.render:
        from prepare_render import main as prepare
        prepare()
        run([tool('picasso'),'-o',out/'shader.shbin',ROOT/'renderer/shader.v.pica'])
        shader=(out/'shader.shbin').read_bytes()
        shader_c=out/'shader.c';shader_c.write_text('const unsigned char shader_shbin[] __attribute__((aligned(4)))={'+','.join(map(str,shader))+'};\nconst unsigned shader_shbin_size='+str(len(shader))+';\n')
        sources += [ROOT/'src/render_bridge.c',ROOT/'src/render_device.c',ROOT/'renderer/gfx_pc.c',ROOT/'renderer/gfx_cc.c',ROOT/'renderer/gfx_citro3d.c',shader_c]
    else:sources.append(ROOT/'src/bringup_render.c')
    for src in sources:
        obj=out/(src.stem+'.o')
        if src.stem in ['game_host','vanilla_policy','render_bridge','gfx_pc','save_layout_check','stereo_camera','bottom_game','wallpaper','control_game']:
            flags=game_flags()
        else:
            flags=[*ARCH,'-std=gnu11','-O2','-g','-D__3DS__','-DSSB_BRINGUP',
                   '-ffunction-sections','-fdata-sections',
                   '-fshort-enums' if src.stem in ['platform_3ds','performance','render_device','gfx_citro3d','bottom_3ds','io_worker'] else '-fno-short-enums',
                   '-I'+str(SDK/'libctru/include'),'-I'+str(UPSTREAM/'port'),
                   '-isystem',str(ARM/'arm-none-eabi/include')]
        flags += ['-I'+str(ROOT/'include'),'-I'+str(ROOT/'renderer')]
        if args.render:flags += ['-DTARGET_N3DS','-DSSB_GRAPHICS']
        if args.release:flags += ['-DSSB_RELEASE']
        run([BIN/'clang.exe',*flags,'-c',src,'-o',obj]);objects.append(obj)
    asm=(UPSTREAM/'port/coroutine_armv7.S').read_text().replace('.fpu    vfpv3-d16','.fpu    vfp')
    (out/'coroutine_arm.S').write_text(asm)
    obj=out/'coroutine_arm.o'
    run([BIN/'clang.exe',*ARCH,'-c',out/'coroutine_arm.S','-o',obj]);objects.append(obj)
    libs=ARM/'arm-none-eabi/lib/armv6k/fpu'
    gcc=ARM/'lib/gcc/arm-none-eabi'/GCC_VERSION/'armv6k/fpu'
    script=(ARM/'arm-none-eabi/lib/3dsx.ld').read_text()
    script=script.replace('data   PT_LOAD FLAGS(6)','tls    PT_TLS FLAGS(4);\n\tdata   PT_LOAD FLAGS(6)')
    for start,end in [('\t.tdata :','\t.tbss :'),('\t.tbss :','\t/*')]:
        a=script.index(start);b=script.index(end,a+len(start))
        script=script[:a]+script[a:b].replace(': data',': data : tls')+script[b:]
    script=script.replace('.bss ALIGN(4)','.bss ALIGN(32)').replace('*(.data.*)','*(.data.*)\n\t\t*(.got .got.*)')
    script += '\nPROVIDE(__text_start = 0x00100000);\n'
    layout=out/'3dsx-lld.ld';layout.write_text(script)
    elf=out/('ssb64-'+variant+'.elf')
    cmd=[BIN/'ld.lld.exe','-T',layout,'--gc-sections','--emit-relocs','--error-limit=0',
         '-Map='+str(out/'ssb64-bringup.map'),libs/'3dsx_crt0.o',gcc/'crti.o',gcc/'crtbegin.o',
         *objects,'-L'+str(SDK/'libctru/lib'),'-L'+str(libs),'-L'+str(gcc),
         '--start-group',OUT/'libssb64-game.a',OUT/'libssb64-support.a',
         '-lstdc++',*(['-lcitro3d'] if args.render else []),'-lctru','-lm','-lc','-lsysbase','-lgcc','--end-group',
         gcc/'crtend.o',gcc/'crtn.o','-o',elf]
    cmd+=['--wrap=abort','--wrap=ftParamUpdatePlayerBattleStats','--wrap=lbCommonDrawSObjAttr']
    cmd+=['--wrap=ftCommonAttackLw4CheckInterruptSquat']
    if args.render:cmd+=['--wrap=portResetStructFixups','--wrap=portEvictStructFixupsInRange']
    p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    (out/'link.log').write_text(p.stdout+p.stderr)
    if p.returncode:
        print((p.stdout+p.stderr)[:11000]);return 1
    romfs=OUT/'romfs';romfs.mkdir(parents=True,exist_ok=True)
    for src in (ROOT/'assets').rglob('*'):
        if src.is_file() and src.suffix in ['.pak','.bin']:
            dst=romfs/src.relative_to(ROOT/'assets');dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists() or dst.stat().st_mtime<src.stat().st_mtime:shutil.copy2(src,dst)
    metadata=bytearray(0x36c0);metadata[:4]=b'SMDH'
    for lang in range(16):
        labels=[(0,'Smash 64' if args.release else 'SSB64 development'),(0x80,'Native New Nintendo 3DS port' if args.release else 'Engine and renderer validation build'),(0x180,'Decompilation and port contributors')]
        for offset,text in labels:
            text=text.encode('utf-16le');base=8+lang*0x200+offset
            metadata[base:base+len(text)]=text
    struct.pack_into('<I',metadata,0x2018,0x7fffffff)
    struct.pack_into('<I',metadata,0x2028,1)
    smdh=out/'bringup.smdh';smdh.write_bytes(metadata)
    run([tool('3dsxtool'),elf,out/('ssb64-'+variant+'.3dsx'),
         '--smdh='+str(smdh),'--romfs='+str(romfs)])
    print('Diagnostic binary:',elf)
    return 0

if __name__=='__main__':sys.exit(main())

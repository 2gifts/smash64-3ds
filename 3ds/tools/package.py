"""Build a private development CIA/CXI for install and launch testing."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import wave
import shutil
import argparse
from PIL import Image, ImageDraw, ImageFont
from build import ROOT,OUT,tool

def run(*args):
    subprocess.run(list(map(str,args)),check=True,cwd=ROOT)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['graphics','release'],default='graphics');args=ap.parse_args()
    dst=OUT/'package';dst.mkdir(parents=True,exist_ok=True)
    shutil.copy2(OUT/args.variant/('ssb64-'+args.variant+'.elf'),dst/'ssb64-package.elf')
    from home_art import prepare
    prepare(dst)
    with wave.open(str(dst/'silent.wav'),'wb') as wav:
        wav.setparams((2,2,32000,0,'NONE','not compressed'));wav.writeframes(bytes(32000*4))
    bt=tool('bannertool')
    makerom=tool('makerom')
    run(bt,'makesmdh','-s','Smash 64' if args.variant=='release' else 'Smash 64 development','-l','Native New Nintendo 3DS port with stereoscopic 3D',
        '-p','Decompilation and port contributors','-i',dst/'icon.png','-o',dst/'icon.smdh',
        '-r','regionfree','-f','visible,allow3d,new3ds,recordusage')
    run(bt,'makebanner','-i',dst/'banner.png','-a',dst/'silent.wav','-o',dst/'banner.bin')
    # Reuse the existing, console-tested homebrew capability profile, with a
    # distinct application identity and this title's private RomFS.
    rsf=(ROOT/'smash64.rsf').read_text()
    rsf+='\nRomFs:\n  RootPath: "'+(OUT/'romfs').as_posix()+'"\n'
    (dst/'smash64.rsf').write_text(rsf)
    common=['-target','t','-exefslogo','-elf',dst/'ssb64-package.elf',
        '-rsf',dst/'smash64.rsf','-icon',dst/'icon.smdh','-banner',dst/'banner.bin']
    for fmt,suffix in [('cia','cia'),('ncch','cxi')]:
        run(makerom,'-f',fmt,*common,*(['-ver','8'] if fmt=='cia' else []),'-o',dst/('smash64-development.'+suffix))
    report={'development_only':args.variant!='release','build_variant':args.variant,'validation_complete':False,'fully_playable':False,'files':{}}
    for path in dst.glob('smash64-development.*'):
        report['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (dst/'package.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

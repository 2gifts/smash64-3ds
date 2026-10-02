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

# Two installable titles that keep separate saves. The fresh-save profile keeps
# the original title ID and SD folder so existing installs update in place.
# Unique IDs stay in the homebrew range (0xF8000-0xFFFFF), far from any retail
# title such as Super Smash Bros. for Nintendo 3DS.
PROFILES={
    'fresh':dict(name='Smash 64',process='Smash64',unique=0xFF640,product='CTR-P-SS64',stem='smash64'),
    'unlocked':dict(name='Smash 64: All Unlocked',process='Smash64U',unique=0xFF641,product='CTR-P-SS6U',stem='smash64-unlocked'),
}
TITLE_VERSION=9
def title_id(profile):return 0x0004000000000000|(PROFILES[profile]['unique']<<8)

def run(*args):
    subprocess.run(list(map(str,args)),check=True,cwd=ROOT)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['graphics','release'],default='graphics');ap.add_argument('--profile',choices=list(PROFILES),default='fresh');args=ap.parse_args()
    profile=PROFILES[args.profile];built=args.variant+('-unlocked' if args.profile=='unlocked' else '')
    dst=OUT/'package'/args.profile;dst.mkdir(parents=True,exist_ok=True)
    shutil.copy2(OUT/built/('ssb64-'+built+'.elf'),dst/'ssb64-package.elf')
    from home_art import prepare
    prepare(dst,args.profile)
    with wave.open(str(dst/'silent.wav'),'wb') as wav:
        wav.setparams((2,2,32000,0,'NONE','not compressed'));wav.writeframes(bytes(32000*4))
    bt=tool('bannertool')
    makerom=tool('makerom')
    run(bt,'makesmdh','-s',profile['name'] if args.variant=='release' else 'Smash 64 development','-l','Native New Nintendo 3DS port with stereoscopic 3D',
        '-p','Decompilation and port contributors','-i',dst/'icon.png','-o',dst/'icon.smdh',
        '-r','regionfree','-f','visible,allow3d,new3ds,recordusage')
    run(bt,'makebanner','-i',dst/'banner.png','-a',dst/'silent.wav','-o',dst/'banner.bin')
    # Reuse the existing, console-tested homebrew capability profile, with a
    # distinct application identity and this title's private RomFS.
    rsf=(ROOT/'smash64.rsf').read_text()
    rsf=rsf.replace('Title: Smash64','Title: '+profile['process']).replace('ProductCode: CTR-P-SS64','ProductCode: '+profile['product']).replace('UniqueId: 0xFF640','UniqueId: '+hex(profile['unique']))
    assert 'UniqueId: '+hex(profile['unique']) in rsf
    rsf+='\nRomFs:\n  RootPath: "'+(OUT/'romfs').as_posix()+'"\n'
    (dst/'smash64.rsf').write_text(rsf)
    common=['-target','t','-exefslogo','-elf',dst/'ssb64-package.elf',
        '-rsf',dst/'smash64.rsf','-icon',dst/'icon.smdh','-banner',dst/'banner.bin']
    for fmt,suffix in [('cia','cia'),('ncch','cxi')]:
        run(makerom,'-f',fmt,*common,*(['-ver',str(TITLE_VERSION)] if fmt=='cia' else []),'-o',dst/(profile['stem']+'.'+suffix))
    report={'development_only':args.variant!='release','build_variant':args.variant,'profile':args.profile,'title_id':f'{title_id(args.profile):016x}','validation_complete':False,'fully_playable':False,'files':{}}
    for path in dst.glob(profile['stem']+'.c*'):
        report['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (dst/'package.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

"""Build the installable CIAs from a locally supplied US ROM (Windows).

Two titles with separate saves are produced:
  build/release/Smash64-New3DS.cia           fresh save (or your imported .srm)
  build/release/Smash64-New3DS-Unlocked.cia  every fighter, stage and option unlocked
"""
import argparse,json,shutil,subprocess,sys
from pathlib import Path

OUTPUTS={'fresh':'Smash64-New3DS.cia','unlocked':'Smash64-New3DS-Unlocked.cia'}

def main():
    root=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--rom',type=Path);ap.add_argument('--save',type=Path)
    ap.add_argument('--profile',choices=['both',*OUTPUTS],default='both');args=ap.parse_args()
    config=root/'build-config.json';cfg=json.loads(config.read_text()) if config.exists() else {}
    if args.rom:cfg['rom']=str(args.rom.resolve())
    if args.save:cfg['save']=str(args.save.resolve())
    config.write_text(json.dumps(cfg,indent=2)+'\n')
    def run(name,*flags):subprocess.run([sys.executable,str(root/'tools'/name),*map(str,flags)],cwd=root,check=True)
    run('build.py','--prepare');run('assets.py')
    if cfg.get('save'):run('import_save.py',cfg['save'])
    else:(root/'assets/initial-save.bin').write_bytes(bytes(32768))
    run('fetch_home_art.py');run('build_support.py')
    target=root/'build/release';target.mkdir(parents=True,exist_ok=True)
    for profile in (OUTPUTS if args.profile=='both' else [args.profile]):
        run('build_runtime.py','--release','--profile',profile)
        run('package.py','--variant','release','--profile',profile);run('verify_package.py','--profile',profile)
        stem='smash64-unlocked' if profile=='unlocked' else 'smash64'
        shutil.copy2(root/'build/package'/profile/(stem+'.cia'),target/OUTPUTS[profile])
        print('Ready to install with FBI:',target/OUTPUTS[profile])
if __name__=='__main__':main()

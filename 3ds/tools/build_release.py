"""Build a private installable CIA from a locally supplied US ROM (Windows)."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path);ap.add_argument('--save',type=Path);args=ap.parse_args()
    config=root/'build-config.json';cfg=json.loads(config.read_text()) if config.exists() else {}
    if args.rom:cfg['rom']=str(args.rom.resolve())
    if args.save:cfg['save']=str(args.save.resolve())
    config.write_text(json.dumps(cfg,indent=2)+'\n')
    def run(name,*flags):subprocess.run([sys.executable,str(root/'tools'/name),*map(str,flags)],cwd=root,check=True)
    run('build.py','--prepare');run('assets.py')
    if cfg.get('save'):run('import_save.py',cfg['save'])
    else:(root/'assets/initial-save.bin').write_bytes(bytes(32768))
    run('fetch_home_art.py');run('build_support.py');run('build_runtime.py','--release')
    run('package.py','--variant','release');run('verify_package.py')
    target=root/'build/release/Smash64-New3DS.cia';shutil.copy2(root/'build/package/smash64-development.cia',target)
    print('Ready to install with FBI:',target)
if __name__=='__main__':main()

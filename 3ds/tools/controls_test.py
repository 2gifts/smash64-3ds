"""Host checks for persisted controls and C-stick hysteresis."""
import json,subprocess
from build import ROOT,OUT,BIN
def main():
    d=OUT/'controls-host';d.mkdir(exist_ok=True)
    code='#define CONTROLS_PATH "'+(d/'controls.cfg').as_posix()+'"\n'
    code+=(ROOT/'src/control_settings.c').read_text()+'\n'+(ROOT/'src/control_input.c').read_text()
    code+='''
#include <assert.h>
uint32_t native_perf_error;
int nativeIoSubmit(NativeIoWrite fn,const void* data,size_t n,unsigned key){assert(key==4);fn(data);return 0;}
static void config(const char* s){FILE* f=fopen(CONTROLS_PATH,"wb");assert(f);fputs(s,f);fclose(f);nativeControlsLoad();}
int main(void){
    remove(CONTROLS_PATH);nativeControlsLoad();assert(!native_tap_jump_disabled&&!native_cstick_enabled);
    assert(!nativeControlsToggle(0)&&!nativeControlsToggle(1));nativeControlsLoad();assert(native_tap_jump_disabled&&native_cstick_enabled);
    config("tap_jump=2\\nc_stick=1\\n");assert(!native_tap_jump_disabled&&!native_cstick_enabled);
    config("tap_jump=0\\nc_stick=1\\nextra");assert(!native_cstick_enabled);
    config("tap_jump=0\\r\\nc_stick=1\\r\\n");assert(native_tap_jump_disabled&&native_cstick_enabled);
    nativeControlsScan(100,0);assert(!native_cstick_direction); // enable while held
    nativeControlsScan(0,0);nativeControlsScan(39,0);assert(!native_cstick_direction);
    nativeControlsScan(40,0);assert(native_cstick_direction==CSTICK_RIGHT);
    for(int i=0;i<500;i++){nativeControlsScan(100,0);assert(!native_cstick_direction);}
    nativeControlsScan(0,100);assert(!native_cstick_direction); // must center first
    nativeControlsScan(23,23);nativeControlsScan(60,100);assert(native_cstick_direction==CSTICK_UP);
    nativeControlsScan(0,0);nativeControlsScan(-100,60);assert(native_cstick_direction==CSTICK_LEFT);
    nativeControlsScan(0,0);nativeControlsScan(0,-100);assert(native_cstick_direction==CSTICK_DOWN);
    nativeControlsToggle(1);nativeControlsScan(0,0);nativeControlsScan(100,0);assert(!native_cstick_direction);
    remove(CONTROLS_PATH);puts("saved settings, defaults, malformed files, deadzone, direction, hysteresis and held-nub behavior passed");
}
'''
    (d/'test.c').write_text(code);exe=d/'test.exe'
    p=subprocess.run([str(BIN/'clang.exe'),'-O2','-I'+str(ROOT/'include'),str(d/'test.c'),'-o',str(exe)],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    p=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
    r=dict(passed=True,detail=p.stdout.strip());(d/'verified.json').write_text(json.dumps(r,indent=2));print(r)
if __name__=='__main__':main()

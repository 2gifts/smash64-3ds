"""Test saved display modes and clipping against the actual portable C code."""
import json,subprocess
from build import ROOT,OUT,BIN

def main():
    dst=OUT/'display-host-test';dst.mkdir(exist_ok=True)
    cfg=(dst/'display.cfg').as_posix()
    source='#define DISPLAY_PATH "'+cfg+'"\n'+(ROOT/'src/display_settings.c').read_text()
    source+='''
int nativeIoSubmit(NativeIoWrite fn,const void* data,size_t n,unsigned key){fn(data);return 0;}
'''
    source+='''
#include <assert.h>
uint32_t native_perf_error;
static void contents(const char* s){FILE* f=fopen(DISPLAY_PATH,"wb");assert(f);fputs(s,f);fclose(f);}
static void closef(float a,float b){assert(fabsf(a-b)<0.0001f);}
int main(void){
    remove(DISPLAY_PATH);nativeDisplayLoad();assert(native_widescreen==0);
    assert(nativeDisplayToggle()==0&&native_widescreen==1);
    native_widescreen=0;nativeDisplayLoad();assert(native_widescreen==1);
    assert(nativeDisplayToggle()==0&&native_widescreen==0);
    native_widescreen=1;nativeDisplayLoad();assert(native_widescreen==0);
    contents("widescreen=1\\r\\n");nativeDisplayLoad();assert(native_widescreen==1);
    const char* invalid[]={"","widescreen=","widescreen=2\\n","widescreen=1\\nextra","widescreen=1"};
    for(unsigned i=0;i<5;i++){contents(invalid[i]);nativeDisplayLoad();assert(native_widescreen==0);}
    int vp[4];float a[4];
    assert(nativeDisplayViewport(10,10,300,220,vp,a));
    assert(vp[0]==0&&vp[1]==40&&vp[2]==240&&vp[3]==320);
    closef(a[0],45.0f/44);closef(a[1],1);closef(a[2],0);closef(a[3],0);
    float mono=nativeDisplayClipScale()*a[0]*320/300;native_widescreen=1;
    closef(nativeDisplayClipScale()*400/300,mono);closef(mono,240.0f/220);
    assert(nativeDisplayViewport(10,10,300,220,vp,a));
    assert(vp[0]==0&&vp[1]==0&&vp[2]==240&&vp[3]==400);
    closef(a[0],1);closef(a[1],1);closef(a[2],0);closef(a[3],0);
    assert(nativeDisplayViewport(0,0,320,240,vp,a));
    assert(vp[0]==0&&vp[1]==0&&vp[2]==240&&vp[3]==400);
    closef(a[0],320.0f/300);closef(a[1],240.0f/220);
    closef(a[2],0);closef(a[3],0);
    /* Validate endpoints of partially clipped miniature viewports. */
    for(int x=-20;x<330;x+=7)for(int y=-20;y<250;y+=9){
        if(!nativeDisplayViewport(x,y,40,40,vp,a))continue;
        assert(vp[0]>=0&&vp[1]>=0&&vp[0]+vp[2]<=240&&vp[1]+vp[3]<=400);
        float left=400-vp[1]-vp[3],bottom=vp[0];
        closef(left+(-a[0]+a[2]+1)*vp[3]/2,nativeDisplayX(x));
        closef(left+( a[0]+a[2]+1)*vp[3]/2,nativeDisplayX(x+40));
        closef(bottom+(-a[1]+a[3]+1)*vp[2]/2,nativeDisplayY(y));
    }
    remove(DISPLAY_PATH);puts("settings persistence, defaults, invalid files, and 1500 clipped viewports passed");
}
'''
    c=dst/'display-host.c';c.write_text(source)
    exe=dst/'display-host.exe'
    subprocess.run([str(BIN/'clang.exe'),'-O2','-I'+str(ROOT/'include'),str(c),'-o',str(exe)],check=True,capture_output=True,text=True)
    result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
    evidence=dict(passed=True,detail=result.stdout.strip())
    (dst/'verified.json').write_text(json.dumps(evidence,indent=2));print(evidence)

if __name__=='__main__':main()

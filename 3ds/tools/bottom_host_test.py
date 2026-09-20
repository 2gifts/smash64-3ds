"""Render the actual C UI with edge-case rosters before emulator integration."""
import hashlib,json,subprocess
from PIL import Image
from build import ROOT,OUT,BIN

def main():
    dst=OUT/'bottom-host-test';dst.mkdir(exist_ok=True)
    code='''
#include "native_bottom.h"
#include "native_perf.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
NativePerfRender native_perf_render={.submit_ms=5.1f,.gpu_previous_ms=3.4f,.draw_calls=310};
float native_bottom_last_ms=0.65f;
unsigned native_tap_jump_disabled,native_cstick_enabled;
static struct {unsigned before[8];uint16_t pixels[320*240];unsigned after[8];} guarded;
static NativeBottomState s;
static void draw(const char* name,unsigned page){
    for(unsigned i=0;i<8;i++)guarded.before[i]=guarded.after[i]=0xdecafbad;
    nativeBottomDraw(guarded.pixels,&s,598,1,page,2,0,1);
    for(unsigned i=0;i<8;i++)assert(guarded.before[i]==0xdecafbad&&guarded.after[i]==0xdecafbad);
    char path[256];snprintf(path,sizeof(path),"build/bottom-host-test/%s.rgb565",name);
    FILE* f=fopen(path,"wb");assert(f);fwrite(guarded.pixels,1,sizeof(guarded.pixels),f);fclose(f);
}
int main(void){
    assert(nativeBottomArtInit("assets/bottom-ui.bin"));
    assert(nativeBottomHit(57,225)==BOTTOM_PERFORMANCE&&nativeBottomHit(160,225)==BOTTOM_DISPLAY&&nativeBottomHit(265,225)==BOTTOM_CONTROLS);
    assert(!nativeBottomHit(160,211)&&!nativeBottomHit(320,225)&&!nativeBottomHit(10,240));
    s=(NativeBottomState){.scene=22,.page=BOTTOM_BATTLE,.stage=6,.status=1,.stock_mode=1,.rule_stocks=4};
    unsigned fighters[4]={8,0,5,9},damage[4]={24,109,0,999};
    for(unsigned i=0;i<4;i++)s.players[i]=(NativeBottomPlayer){.kind=i?1:0,.character=fighters[i],.color=i,.damage=damage[i],.stocks=4-i,.stock_limited=1,.level=9,.ready=1};
    draw("four-stock",0);
    s.players[0].combo_hits=12;s.players[0].combo_active=1;draw("combo-active",0);
    s.players[0].combo_active=0;draw("combo-ended",0);s.players[0].combo_hits=0;
    s.players[1].stocks=0;draw("eliminated",0);
    s.players[1].stocks=99;draw("large-stock-count",0);
    for(unsigned i=0;i<4;i++){s.players[i].stock_limited=0;s.players[i].kos=i+1;s.players[i].falls=i;}
    s.stock_mode=0;s.timer=1;s.seconds=87;draw("four-time",0);
    s.players[2].kind=s.players[3].kind=2;draw("two-time",0);
    s.page=BOTTOM_SELECT;s.scene=16;s.players[0].character=10;draw("select",0);
    s.players[0].ready=0;s.players[0].character=~0u;draw("select-unpicked",0);
    s.page=BOTTOM_RESULTS;for(unsigned i=0;i<4;i++){s.players[i].kind=i?1:0;s.players[i].character=fighters[i];s.players[i].place=i+1;}
    draw("results",0);
    s.page=BOTTOM_STAGE;draw("stage",0);
    s.page=BOTTOM_MENU;s.scene=7;draw("menu",0);
    draw("controls",BOTTOM_CONTROLS);
    native_tap_jump_disabled=native_cstick_enabled=1;draw("controls-enabled",BOTTOM_CONTROLS);
    draw("guide",BOTTOM_GUIDE);draw("performance",BOTTOM_PERFORMANCE);
    assert(nativeBottomControlsHit(100,55)==BOTTOM_TAP_JUMP);
    assert(nativeBottomControlsHit(100,115)==BOTTOM_CSTICK);
    assert(nativeBottomControlsHit(100,175)==BOTTOM_GUIDE);
    assert(!nativeBottomControlsHit(100,96)&&!nativeBottomControlsHit(320,55));
    nativeBottomArtExit();puts("real C compositor: bounds, touch targets, stock/time/elimination/results and menu states passed");
}
'''
    c=dst/'bottom-host.c';c.write_text(code)
    exe=dst/'bottom-host.exe'
    subprocess.run([str(BIN/'clang.exe'),'-std=c11','-O2','-I'+str(ROOT/'include'),str(c),str(ROOT/'src/bottom_draw.c'),'-o',str(exe)],check=True,capture_output=True,text=True)
    run=subprocess.run([str(exe)],cwd=ROOT,check=True,capture_output=True,text=True)
    for path in dst.glob('*.rgb565'):
        raw=path.read_bytes();im=Image.new('RGB',(320,240));pix=im.load()
        for x in range(320):
            for y in range(240):
                off=(x*240+239-y)*2;v=int.from_bytes(raw[off:off+2],'little');pix[x,y]=((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31)
        im.save(path.with_suffix('.png'))
    r=dict(passed=True,detail=run.stdout.strip(),art_sha256=hashlib.sha256((ROOT/'assets/bottom-ui.bin').read_bytes()).hexdigest(),screens=sorted(p.stem for p in dst.glob('*.rgb565')))
    (dst/'verified.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))

if __name__=='__main__':main()

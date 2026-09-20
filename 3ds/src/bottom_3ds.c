#include <3ds.h>
#include <citro3d.h>
#include <string.h>
#include <stdio.h>
#include "native_bottom.h"
#include "native_display.h"
#include "native_perf.h"
#include "native_controls.h"
extern volatile uint32_t ssb_frame_count;
uint16_t native_bottom_pixels[320*240] __attribute__((aligned(32)));
NativeBottomState native_bottom_observed;
uint32_t native_bottom_redraws,native_bottom_page;
float native_bottom_last_ms;
volatile uint32_t native_test_bottom_disabled;
static NativeBottomState previous;
static uint32_t lastFrame,lastVblank=~0u,lastFps=~0u,lastWide=~0u,lastReports,lastErrors,lastAudio;
static unsigned ready,dirty=1,settingError;
static unsigned vblank(void){
#ifdef SSB_GRAPHICS
    return C3D_FrameCounter(1);
#else
    return ssb_frame_count;
#endif
}
static void present(void){
    void* fb=gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,NULL,NULL);
    memcpy(fb,native_bottom_pixels,sizeof(native_bottom_pixels));GSPGPU_FlushDataCache(fb,sizeof(native_bottom_pixels));
    gfxScreenSwapBuffers(GFX_BOTTOM,false);lastVblank=vblank();
}
void nativeBottomInit(void){
    if(!nativeBottomArtInit("romfs:/bottom-ui.bin")){printf("Bottom screen art unavailable\n");return;}
    ready=1;gfxSetDoubleBuffering(GFX_BOTTOM,true);
    NativeBottomState s={0};s.scene=1;s.status=~0u;
    nativeBottomDraw(native_bottom_pixels,&s,0,native_widescreen,0,0,0,1);present();
}
void nativeBottomTouch(unsigned x,unsigned y){
    if(!ready)return;
    if(native_bottom_page==BOTTOM_CONTROLS){
        unsigned option=nativeBottomControlsHit(x,y);
        if(option==BOTTOM_TAP_JUMP||option==BOTTOM_CSTICK){settingError=nativeControlsToggle(option==BOTTOM_CSTICK)!=0;dirty=1;return;}
        if(option==BOTTOM_GUIDE){native_bottom_page=BOTTOM_GUIDE;dirty=1;return;}
    }
    unsigned hit=nativeBottomHit(x,y);
    if(hit==BOTTOM_DISPLAY){settingError=nativeDisplayToggle()!=0;dirty=1;}
    else if(hit){native_bottom_page=native_bottom_page==BOTTOM_GUIDE&&hit==BOTTOM_CONTROLS?BOTTOM_CONTROLS:native_bottom_page==hit?BOTTOM_NONE:hit;dirty=1;}
}
void nativeBottomFrame(unsigned fps,unsigned audio){
    native_perf_render.bottom_ms=0;
    if(!ready||native_test_bottom_disabled)return;
    NativeBottomState state;nativeBottomSnapshot(&state);native_bottom_observed=state;
    unsigned reports=__atomic_load_n(&native_perf_saved,__ATOMIC_RELAXED);
    unsigned errors=__atomic_load_n(&native_perf_error,__ATOMIC_RELAXED)+settingError;
    if(state.scene!=previous.scene){native_bottom_page=0;dirty=1;}
    if(fps!=lastFps||native_widescreen!=lastWide||reports!=lastReports||
       errors!=lastErrors||audio!=lastAudio||
       (!native_bottom_page&&memcmp(&state,&previous,sizeof(state))))dirty=1;
    if(native_bottom_page==BOTTOM_PERFORMANCE&&ssb_frame_count-lastFrame>=30)dirty=1;
    /* Cap the secondary LCD to 30 updates/s, and never wait for it. Both LCD
     * buffers are separate from the top-screen PICA targets. Static pages
     * redraw only on changes (including the half-second FPS sample). */
    if(!dirty||ssb_frame_count-lastFrame<2||lastVblank==vblank())return;
    uint64_t start=svcGetSystemTick();
    nativeBottomDraw(native_bottom_pixels,&state,fps,native_widescreen,native_bottom_page,
        reports,errors,audio);present();
    native_perf_render.bottom_ms=(svcGetSystemTick()-start)*(1000.0f/SYSCLOCK_ARM11);
    native_bottom_last_ms=native_perf_render.bottom_ms;
    native_bottom_redraws++;lastFrame=ssb_frame_count;previous=state;
    lastFps=fps;lastWide=native_widescreen;lastReports=reports;lastErrors=errors;lastAudio=audio;dirty=0;
}
void nativeBottomExit(void){nativeBottomArtExit();ready=0;}

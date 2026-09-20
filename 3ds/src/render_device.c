#include "gfx_3ds.h"
#include "gfx_rendering_api.h"
#include "gfx_window_manager_api.h"
#include <stdio.h>
#include "native_perf.h"
#include "native_bottom.h"
static uint64_t renderStart;
extern void gfx_init(struct GfxWindowManagerAPI*,struct GfxRenderingAPI*,const char*,bool);
extern struct GfxRenderingAPI gfx_citro3d_api;
Gfx3DSMode gGfx3DSMode;
C3D_RenderTarget *gTarget,*gTargetRight;
float gSliderLevel;
volatile float native_test_slider=-1.0f;
bool gGfx3DEnabled;
int uLoc_projection,uLoc_modelView;
int uLoc_eye;
extern volatile uint32_t ssb_frame_count;
volatile uint32_t native_capture_requested;
#ifdef SSB_RELEASE
volatile uint32_t native_test_no_capture=1;
#else
volatile uint32_t native_test_no_capture;
#endif
static u8* captureBuffer[2];
static bool renderReady;
static void empty(void){}
static void init(const char*t,bool f){}
static void dimensions(uint32_t*w,uint32_t*h){*w=320;*h=240;}
static bool start(void){return true;}
static struct GfxWindowManagerAPI window={.init=init,.get_dimensions=dimensions,.handle_events=empty,.start_frame=start,.swap_buffers_begin=empty,.swap_buffers_end=empty};
void nativeRenderInit(void) {
    if(!C3D_Init(2*1024*1024))abort();
    renderReady=true;
    gfxSet3D(true);
    C3D_DEPTHTYPE depth={.__i=GPU_RB_DEPTH24_STENCIL8};
    gTarget=C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,depth);
    gTargetRight=C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,depth);
    if(!gTarget||!gTargetRight)abort();
    uint32_t flags=GX_TRANSFER_FLIP_VERT(0)|GX_TRANSFER_OUT_TILED(0)|GX_TRANSFER_RAW_COPY(0)|GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8)|GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8)|GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO);
    C3D_RenderTargetSetOutput(gTarget,GFX_TOP,GFX_LEFT,flags);
    C3D_RenderTargetSetOutput(gTargetRight,GFX_TOP,GFX_RIGHT,flags);
    gfx_init(&window,&gfx_citro3d_api,"Smash 64 native",false);
}
void nativeRenderShutdown(void) {
    if(!renderReady)return;
    /* Wait for GPU work, detach APT/VBlank callbacks, and destroy the targets
     * before libctru releases the framebuffers and application heaps. */
    C3D_Fini();renderReady=false;gTarget=gTargetRight=NULL;
}
void nativeRenderBegin(void) {
    renderStart=svcGetSystemTick();
    gSliderLevel=osGet3DSliderState();gGfx3DEnabled=gSliderLevel>0.0f;
    if(native_test_slider>=0.0f){gSliderLevel=native_test_slider;gGfx3DEnabled=gSliderLevel>0.0f;}
    captureBuffer[0]=gfxGetFramebuffer(GFX_TOP,GFX_LEFT,NULL,NULL);
    captureBuffer[1]=gfxGetFramebuffer(GFX_TOP,GFX_RIGHT,NULL,NULL);
}
void nativeRenderCapture(void) {
    native_perf_render.render_total_ms=(svcGetSystemTick()-renderStart)*(1000.0f/SYSCLOCK_ARM11);
    if(native_test_no_capture&&!native_capture_requested)return;
    if(ssb_frame_count!=30&&ssb_frame_count!=120&&ssb_frame_count!=360&&ssb_frame_count%300!=290&&!native_capture_requested)return;
    native_capture_requested=0;C3D_FrameSync();
    for(unsigned eye=0;eye<(gGfx3DEnabled?2:1);eye++) {
        u8* pixels=captureBuffer[eye];
        GSPGPU_InvalidateDataCache(pixels,400*240*3);
        char path[128];snprintf(path,sizeof(path),"sdmc:/3ds/ssb64/frame-%06u-%u.ppm",ssb_frame_count,eye);
        FILE* f=fopen(path,"wb");if(!f)continue;
        fprintf(f,"P6\n400 240\n255\n");
        u8 row[400*3];
        for(int y=0;y<240;y++) {
            for(int x=0;x<400;x++) {
                const u8* p=pixels+(x*240+239-y)*3;
                row[x*3]=p[2];row[x*3+1]=p[1];row[x*3+2]=p[0];
            }
            fwrite(row,1,sizeof(row),f);
        }
        fclose(f);port_log("Captured %s\n",path);
    }
    /* Diagnostic capture of the RGB565 text console; disabled in normal play. */
    const u16* bottom=native_bottom_pixels;
    char path[128];snprintf(path,sizeof(path),"sdmc:/3ds/ssb64/frame-%06u-bottom.ppm",ssb_frame_count);
    FILE* f=fopen(path,"wb");
    if(f){
        fprintf(f,"P6\n320 240\n255\n");
        u8 row[320*3];
        for(unsigned y=0;y<240;y++){
            for(unsigned x=0;x<320;x++){
                u16 p=bottom[x*240+239-y];
                row[x*3]=((p>>11)&31)*255/31;
                row[x*3+1]=((p>>5)&63)*255/63;
                row[x*3+2]=(p&31)*255/31;
            }
            fwrite(row,1,sizeof(row),f);
        }
        fclose(f);
    }
}
/* The game's results transitions sample an N64-sized photograph. This is a
 * scene-change operation, so read back only on demand; gameplay stays on GPU. */
int nativeReadbackPhoto(void* destination,unsigned bytes,float u0,float v0,float u1,float v1) {
    if(!destination||!captureBuffer[0])return -1;
    unsigned w=(unsigned)lroundf(fabsf(u1-u0)*320.0f);
    unsigned h=(unsigned)lroundf(fabsf(v1-v0)*240.0f);
    if(!w||!h||w>320||h>240||bytes!=w*h*2)return -1;
    C3D_FrameSync();
    GSPGPU_InvalidateDataCache(captureBuffer[0],400*240*3);
    u8* out=destination;
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
        int sx=(int)floorf(nativeDisplayX(320*(u0+(x+0.5f)*(u1-u0)/w)));
        int sy=(int)floorf(nativeDisplayY(240*(v0+(y+0.5f)*(v1-v0)/h)));
        int left=native_widescreen?0:40,right=native_widescreen?399:359;
        if(sx<left)sx=left;if(sx>right)sx=right;if(sy<0)sy=0;if(sy>239)sy=239;
        const u8* p=captureBuffer[0]+(sx*240+239-sy)*3;
        unsigned pixel=((p[2]>>3)<<11)|((p[1]>>3)<<6)|((p[0]>>3)<<1)|1;
        *out++=pixel>>8;*out++=pixel;
    }
    port_log("PHOTO frame=%u size=%ux%u region=%.4f,%.4f,%.4f,%.4f\n",ssb_frame_count,w,h,u0,v0,u1,v1);
    return 0;
}

/* Preserve draw order within each eye, while preparing geometry only once.
 * Texture objects are copied because sampler state can change later in a frame.
 * Replaced texture allocations survive until the GPU completes both eyes. */
#include "native_perf.h"
unsigned native_depth_mask,native_stencil_ref,native_alpha_threshold;
volatile uint32_t native_test_magnifier_capture,native_magnifier_draws;
typedef struct NativeDraw {
    int first,count;
    C3D_TexEnv env[6];
    C3D_Tex tex[2];
    int viewport[4],clip[4];
    float adjust[4];
    float shift,focus;
    uint32_t fogColor;
    uint8_t textures,fogIndex;
    uint8_t stencilRef,alphaThreshold,maskWrite;
    bool clipOn,depth,depthWrite,decal,blend,fog,edge;
} NativeDraw;
static NativeDraw nativeDraws[4096];
static unsigned nativeDrawCount;
static unsigned nativeQueuedDraws;
static void* nativeRightColor;
/* Diagnostic switch for matched cached/uncached render comparisons. */
volatile uint32_t native_test_uncached_state;
static C3D_Tex nativeRetiredTextures[4096];
static unsigned nativeRetiredCount;
/* Most batches reuse one of the full-screen/HUD/main camera viewports. Cache
 * wide mapping at batch level so no divisions are repeated per eye or vertex. */
static struct {int key[5],vp[4],valid;float adjust[4];} wideViewports[8];
static unsigned nextWideViewport;
static int nativeMapViewport(NativeDraw* p){
    int key[5]={viewport_x,viewport_y,viewport_width,viewport_height,native_widescreen};
    unsigned i;
    for(i=0;i<8;i++)if(!memcmp(key,wideViewports[i].key,sizeof(key)))break;
    if(i==8){
        i=nextWideViewport++%8;memcpy(wideViewports[i].key,key,sizeof(key));
        wideViewports[i].valid=nativeDisplayViewport(key[0],key[1],key[2],key[3],wideViewports[i].vp,wideViewports[i].adjust);
    }
    memcpy(p->viewport,wideViewports[i].vp,sizeof(p->viewport));
    memcpy(p->adjust,wideViewports[i].adjust,sizeof(p->adjust));
    return wideViewports[i].valid;
}
static void nativeMapScissor(NativeDraw* p){
    static int last[5],mapped[4];
    int key[5]={scissor_x,scissor_y,scissor_width,scissor_height,native_widescreen};
    if(memcmp(last,key,sizeof(key))){
        memcpy(last,key,sizeof(key));
        mapped[0]=nativeDisplayClamp((int)lroundf(nativeDisplayY(scissor_y)),240);
        mapped[1]=400-nativeDisplayClamp((int)lroundf(nativeDisplayX(scissor_width)),400);
        mapped[2]=nativeDisplayClamp((int)lroundf(nativeDisplayY(scissor_height)),240);
        mapped[3]=400-nativeDisplayClamp((int)lroundf(nativeDisplayX(scissor_x)),400);
        if(!native_widescreen){if(mapped[1]<40)mapped[1]=40;if(mapped[3]>360)mapped[3]=360;}
    }
    memcpy(p->clip,mapped,sizeof(p->clip));
}

static void nativeRetireTexture(C3D_Tex* texture) {
    if(nativeRetiredCount==4096){port_log("Retired texture queue exhausted\n");abort();}
    nativeRetiredTextures[nativeRetiredCount++]=*texture;
}
static void nativeQueueBegin(void) {
    /* Called after C3D_FRAME_SYNCDRAW has completed the previous GPU submission. */
    for(unsigned i=0;i<nativeRetiredCount;i++)C3D_TexDelete(&nativeRetiredTextures[i]);
    nativeRetiredCount=0;nativeDrawCount=0;nativeQueuedDraws=0;
    native_perf_render.upload_bytes=0;
}
static void nativeQueueDraw(int first,int count) {
    if(nativeDrawCount==4096){port_log("Draw queue exhausted\n");abort();}
    NativeDraw* p=&nativeDraws[nativeDrawCount++];
    nativeQueuedDraws++;
    const struct CCFeatures* cc=&sShaderProgramPool[sCurShader].cc_features;
    nativeApplyFirstCycle(cc->opt_alpha,cc->num_inputs);
    p->first=first;p->count=count;p->textures=0;
    for(unsigned i=0;i<6;i++)p->env[i]=*C3D_GetTexEnv(i);
    for(unsigned i=0;i<2;i++)if(cc->used_textures[i]){
        p->textures|=1<<i;p->tex[i]=sTexturePool[sTexUnits[i]];
    }
    if(!nativeMapViewport(p)){
        nativeDrawCount--;return;
    }
    nativeMapScissor(p);
    p->clipOn=scissor;p->depth=sDepthTestOn;p->depthWrite=sDepthUpdateOn;
    p->decal=sDepthDecal;p->blend=sUseBlend;
    p->fog=cc->opt_fog;p->fogColor=fog_color;p->fogIndex=current_fog_idx;
    p->edge=cc->opt_texture_edge&&cc->opt_alpha;
    p->maskWrite=native_depth_mask;p->stencilRef=native_stencil_ref;
    p->alphaThreshold=native_alpha_threshold;
    if(p->maskWrite){
        native_magnifier_draws++;
        if(native_test_magnifier_capture){
            extern volatile uint32_t native_capture_requested,ssb_frame_count;
            native_test_magnifier_capture--;native_capture_requested=1;
            port_stats("MAGNIFIER frame=%u stencil=%u\n",ssb_frame_count,p->stencilRef);
        }
        /* N64 writes a white-inside/black-outside image into compressed Z.
         * Mark the interior in PICA stencil and clear only its depth to far.
         * This reuses the game's quad and texture; no framebuffer readback. */
        C3D_TexEnv* e=&p->env[5];C3D_TexEnvInit(e);
        C3D_TexEnvFunc(e,C3D_Alpha,GPU_REPLACE);
        C3D_TexEnvSrc(e,C3D_Alpha,GPU_TEXTURE0,GPU_PREVIOUS,GPU_PREVIOUS);
        C3D_TexEnvOpAlpha(e,GPU_TEVOP_A_SRC_R,GPU_TEVOP_A_SRC_ALPHA,GPU_TEVOP_A_SRC_ALPHA);
        p->fog=false;
    }
    p->shift=s2DMode&&!native_stereo_backdrop?0.0f:gSliderLevel*NATIVE_STEREO_SHIFT_MAX*nativeDisplayClipScale();
    /* Zero focus puts the wallpaper at the far disparity limit. Every
     * perspective point with positive W and focus is strictly in front of
     * this plane, even when the match camera zooms or changes stages. */
    p->focus=native_stereo_backdrop?0.0f:native_stereo_focus_w;
    if(nativeDrawCount>1&&!native_test_uncached_state){
        NativeDraw* a=p-1;
        /* Join contiguous triangles only when all visible state agrees.
         * Vertex colors and texture coordinates remain in the original VBO. */
        if(a->first+a->count==p->first&&a->textures==p->textures&&
           !memcmp(a->env,p->env,sizeof(p->env))&&
           (!(p->textures&1)||!memcmp(&a->tex[0],&p->tex[0],sizeof(C3D_Tex)))&&
           (!(p->textures&2)||!memcmp(&a->tex[1],&p->tex[1],sizeof(C3D_Tex)))&&
           !memcmp(a->viewport,p->viewport,sizeof(p->viewport))&&a->clipOn==p->clipOn&&
           !memcmp(a->adjust,p->adjust,sizeof(p->adjust))&&
           (!p->clipOn||!memcmp(a->clip,p->clip,sizeof(p->clip)))&&
           a->depth==p->depth&&a->depthWrite==p->depthWrite&&a->decal==p->decal&&a->blend==p->blend&&
           a->fog==p->fog&&(!p->fog||(a->fogColor==p->fogColor&&a->fogIndex==p->fogIndex))&&
           a->edge==p->edge&&a->alphaThreshold==p->alphaThreshold&&
           a->maskWrite==p->maskWrite&&a->stencilRef==p->stencilRef&&
           a->shift==p->shift&&(p->shift==0||a->focus==p->focus)){
            a->count+=p->count;nativeDrawCount--;
        }
    }
}
static void nativeQueueRender(void) {
    uint64_t replayStart=svcGetSystemTick();
    bool stereo=false;
    for(unsigned j=0;j<nativeDrawCount;j++)if(nativeDraws[j].shift!=0.0f){stereo=true;break;}
    unsigned eyes=gGfx3DEnabled&&(stereo||native_test_uncached_state)?2:1;
    native_perf_render.batches=nativeQueuedDraws;native_perf_render.vertices=sBufIdx;
    native_perf_render.draw_calls=nativeDrawCount*eyes;
    native_perf_render.texture_binds=0;native_perf_render.fog_uploads=0;
    native_perf_render.eyes=eyes;native_perf_render.slider=gSliderLevel;
    native_perf_render.gpu_previous_ms=C3D_GetDrawingTime();
    C3D_RenderTargetClear(gTarget,C3D_CLEAR_ALL,0x000000ff,0xffffffff);
    if(eyes==2)C3D_RenderTargetClear(gTargetRight,C3D_CLEAR_ALL,0x000000ff,0xffffffff);
    nativeRightColor=gTargetRight->frameBuf.colorBuf;
    if(gGfx3DEnabled&&eyes==1){
        /* Present the same completed color buffer to both LCD eye buffers.
         * The right target retains ownership of its own allocation; restore
         * that pointer after FrameEnd has queued the display transfers. */
        gTargetRight->frameBuf.colorBuf=gTarget->frameBuf.colorBuf;
        gTargetRight->used=true;
    }
    for(unsigned eye=0;eye<eyes;eye++) {
        C3D_RenderTarget* target=eye?gTargetRight:gTarget;
        target->used=true;C3D_SetFrameBuf(&target->frameBuf);
        C3D_Tex* bound[2]={NULL,NULL};
        for(unsigned j=0;j<nativeDrawCount;j++){
            NativeDraw* p=&nativeDraws[j];
            NativeDraw* previous=j&&!native_test_uncached_state?&nativeDraws[j-1]:NULL;
            bool viewportChanged=!previous||memcmp(previous->viewport,p->viewport,sizeof(p->viewport));
            if(viewportChanged)
                C3D_SetViewport(p->viewport[0],p->viewport[1],p->viewport[2],p->viewport[3]);
            if(!previous||memcmp(previous->adjust,p->adjust,sizeof(p->adjust))){
                /* The model matrix rotates (x,y) to (y,-x). Fold the viewport
                 * compensation into the existing projection: no new shader ops. */
                C3D_Mtx m;Mtx_Identity(&m);
                m.r[0].x=p->adjust[1];m.r[1].y=p->adjust[0];
                m.r[0].w=p->adjust[3];m.r[1].w=-p->adjust[2];
                C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,uLoc_projection,&m);
            }
            /* SetViewport invalidates scissor even when the rectangle agrees. */
            if(viewportChanged||p->clipOn!=previous->clipOn||
               (p->clipOn&&memcmp(previous->clip,p->clip,sizeof(p->clip))))
                C3D_SetScissor(p->clipOn?GPU_SCISSOR_NORMAL:GPU_SCISSOR_DISABLE,p->clip[0],p->clip[1],p->clip[2],p->clip[3]);
            for(unsigned i=0;i<6;i++)if(!previous||memcmp(&previous->env[i],&p->env[i],sizeof(C3D_TexEnv)))C3D_SetTexEnv(i,&p->env[i]);
            for(unsigned i=0;i<2;i++)if(p->textures&(1<<i)){
                if(native_test_uncached_state||!bound[i]||memcmp(bound[i],&p->tex[i],sizeof(C3D_Tex))){
                    C3D_TexBind(i,&p->tex[i]);bound[i]=&p->tex[i];native_perf_render.texture_binds++;
                }
            }
            if(!previous||p->depth!=previous->depth||p->depthWrite!=previous->depthWrite||p->maskWrite||previous->maskWrite)
                C3D_DepthTest(p->maskWrite||p->depth,p->maskWrite?GPU_ALWAYS:GPU_LEQUAL,
                    p->maskWrite?GPU_WRITE_DEPTH:p->depthWrite?GPU_WRITE_ALL:GPU_WRITE_COLOR);
            if(!previous||p->stencilRef!=previous->stencilRef||p->maskWrite!=previous->maskWrite){
                C3D_StencilTest(p->stencilRef!=0,p->maskWrite?GPU_ALWAYS:GPU_EQUAL,
                    p->stencilRef,255,p->maskWrite?255:0);
                C3D_StencilOp(GPU_STENCIL_KEEP,GPU_STENCIL_KEEP,p->maskWrite?GPU_STENCIL_REPLACE:GPU_STENCIL_KEEP);
            }
            if(!previous||p->decal!=previous->decal)C3D_DepthMap(true,-1.0f,p->decal?-0.001f:0.0f);
            if(!previous||p->blend!=previous->blend)C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,
                p->blend?GPU_SRC_ALPHA:GPU_ONE,p->blend?GPU_ONE_MINUS_SRC_ALPHA:GPU_ZERO,
                p->blend?GPU_SRC_ALPHA:GPU_ONE,p->blend?GPU_ONE_MINUS_SRC_ALPHA:GPU_ZERO);
            unsigned threshold=p->maskWrite?127:p->edge&&p->alphaThreshold<77?77:p->alphaThreshold;
            unsigned oldThreshold=previous?(previous->maskWrite?127:previous->edge&&previous->alphaThreshold<77?77:previous->alphaThreshold):~0u;
            if(threshold!=oldThreshold)C3D_AlphaTest(true,GPU_GREATER,threshold);
            if(!previous||p->fog!=previous->fog)C3D_FogGasMode(p->fog?GPU_FOG:GPU_NO_FOG,GPU_PLAIN_DENSITY,p->fog);
            if(p->fog){
                if(!previous||!previous->fog||p->fogColor!=previous->fogColor)C3D_FogColor(p->fogColor);
                if(!previous||!previous->fog||p->fogIndex!=previous->fogIndex){
                    C3D_FogLutBind(&fog_lut[p->fogIndex].lut);native_perf_render.fog_uploads++;
                }
            }
            float shift=gGfx3DEnabled?p->shift*(eye?1.0f:-1.0f):0.0f;
            if(!previous||p->shift!=previous->shift||(shift!=0&&p->focus!=previous->focus))
                C3D_FVUnifSet(GPU_VERTEX_SHADER,uLoc_eye,shift,-shift*p->focus,0,0);
            C3D_DrawArrays(GPU_TRIANGLES,p->first,p->count);
        }
    }
    native_perf_render.replay_ms=(svcGetSystemTick()-replayStart)*(1000.0f/SYSCLOCK_ARM11);
    native_perf_render.command_bytes=gpuCmdBufOffset*4;
    extern volatile uint32_t ssb_frame_count;
    if(ssb_frame_count%180==0)port_stats("RENDER frame=%u batches=%u vertices=%d cpu_ms=%.3f gpu_ms=%.3f eyes=%u\n",
        ssb_frame_count,nativeDrawCount,sBufIdx,C3D_GetProcessingTime(),C3D_GetDrawingTime(),eyes);
}
static void nativeQueueEnd(void){gTargetRight->frameBuf.colorBuf=nativeRightColor;}

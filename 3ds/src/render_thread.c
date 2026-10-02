#include <3ds.h>
#include <stdint.h>
#include "native_render_thread.h"
extern void nativeRenderDisplayList(void*);
extern void port_log(const char*,...);
/* On the New 3DS the display list is translated on the third CPU core, as
 * the N64's RCP drew while its CPU went on. The main thread keeps the
 * original order of events: the scheduler's "task done" still arrives on
 * the next simulated vblank, and nothing but the scheduler, audio and
 * controller threads runs until the frame is translated (game_host.c), so
 * the game never changes memory the renderer is reading. Every renderer
 * entry point the game uses waits for the translation first.
 *
 * A frame has two stages. Translation reads game memory (display list,
 * vertices, textures, asset fixups). After it, the renderer replays its own
 * queued draws for each eye and submits them to the GPU; the game may run
 * during that stage. All citro3d calls happen on the render thread while it
 * exists, so the next frame, photo capture and HOME suspend wait for both. */
static Thread renderThread;
static LightEvent renderGo,renderDone;
static void* volatile renderPending;
static volatile int renderBusy,renderTranslating,renderStop;
static uint64_t submittedTick;
int native_render_async;
#ifdef SSB_BENCH
volatile uint32_t native_test_sync_render;
#endif
uint64_t native_render_block_ticks,native_render_tick_start,native_render_submit_ticks,native_render_work_ticks;
static void renderMain(void* unused) {
    for(;;){
        LightEvent_Wait(&renderGo);
        if(renderStop)return;
        uint64_t start=svcGetSystemTick();
        nativeRenderDisplayList(renderPending);
        native_render_work_ticks+=svcGetSystemTick()-start;
        __atomic_store_n(&renderTranslating,0,__ATOMIC_RELEASE);
        __atomic_store_n(&renderBusy,0,__ATOMIC_RELEASE);
        LightEvent_Signal(&renderDone);
    }
}
/* Called by the renderer once the frame no longer reads game memory. */
void nativeRenderTranslated(void) {
    if(!renderThread||threadGetCurrent()!=renderThread)return;
    __atomic_store_n(&renderTranslating,0,__ATOMIC_RELEASE);
    LightEvent_Signal(&renderDone);
}
static void waitFor(volatile int* flag) {
    if(!renderThread||threadGetCurrent()==renderThread)return;
    if(!__atomic_load_n(flag,__ATOMIC_ACQUIRE))return;
    uint64_t start=svcGetSystemTick();
    while(__atomic_load_n(flag,__ATOMIC_ACQUIRE))LightEvent_Wait(&renderDone);
    native_render_block_ticks+=svcGetSystemTick()-start;
}
void nativeRenderWait(void) {waitFor(&renderTranslating);}
void nativeRenderIdle(void) {waitFor(&renderBusy);}
static void renderStart(void) {
    static int tried;
    if(tried)return;
    tried=1;
    bool isNew=false;APT_CheckNew3DS(&isNew);
#ifdef SSB_BENCH
    if(native_test_sync_render)return;
#endif
    if(!isNew)return;
    LightEvent_Init(&renderGo,RESET_ONESHOT);LightEvent_Init(&renderDone,RESET_ONESHOT);
    s32 priority=0x30;svcGetThreadPriority(&priority,CUR_THREAD_HANDLE);
    renderThread=threadCreate(renderMain,NULL,256*1024,priority,2,false);
    native_render_async=renderThread!=NULL;
    port_log("RENDER thread on core 2: %s\n",renderThread?"yes":"unavailable, rendering on the main thread");
}
/* HOME Menu, POWER menu and sleep: citro3d's own APT hook drains and clears
 * the GPU queue on suspend, which must not happen while this thread is still
 * submitting a frame (melee-3ds issue #5). Hooks run newest first, so this
 * one is registered after the first frame, once C3D_Init has added its own. */
static aptHookCookie renderAptHook;
static int renderHooked;
static void renderAptEvent(APT_HookType hook,void* unused) {
    if(hook==APTHOOK_ONSUSPEND||hook==APTHOOK_ONSLEEP||hook==APTHOOK_ONEXIT)nativeRenderIdle();
}
void native_submit_display_list(void* dl) {
    static int frames;
    renderStart();
    if(!renderThread){nativeRenderDisplayList(dl);return;}
    nativeRenderIdle();
    if(frames++==1){aptHook(&renderAptHook,renderAptEvent,NULL);renderHooked=1;}
    native_render_submit_ticks+=svcGetSystemTick()-native_render_tick_start;
    submittedTick=native_render_tick_start;
    renderPending=dl;
    __atomic_store_n(&renderTranslating,1,__ATOMIC_RELEASE);
    __atomic_store_n(&renderBusy,1,__ATOMIC_RELEASE);
    LightEvent_Signal(&renderGo);
}
void nativeRenderStop(void) {
    if(!renderThread)return;
    nativeRenderIdle();
    if(renderHooked){aptUnhook(&renderAptHook);renderHooked=0;}
    renderStop=1;LightEvent_Signal(&renderGo);
    threadJoin(renderThread,U64_MAX);threadFree(renderThread);renderThread=NULL;
}
/* Renderer stage timing for bench builds (tools/prepare_render.py profile). */
uint64_t native_prof_ticks[8];
unsigned long long nativeProfTick(void) {return svcGetSystemTick();}
void nativeProfAdd(unsigned id,unsigned long long ticks) {if(id<8)native_prof_ticks[id]+=ticks;}
/* The audio thread synthesizes once per tic. With a render thread, let it
 * wait (yield) until this tic's frame has been handed over, so synthesis
 * runs while that frame is drawn. The service loop resumes every thread
 * several rounds per tic and the frame is usually ready in the second; after
 * three rounds without one (loading, lag) synthesis runs anyway. */
extern void port_coroutine_yield(void);
void portAudioBeforeSynthesis(void) {
    if(!renderThread)return;
    for(unsigned round=0;round<3&&submittedTick!=native_render_tick_start;round++)port_coroutine_yield();
}

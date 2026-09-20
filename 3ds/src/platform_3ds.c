#include <3ds.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <stdint.h>
#include <errno.h>
#include <malloc.h>
#include "native_perf.h"
#include "native_display.h"
#include "native_bottom.h"
#include "native_io.h"
#include "native_controls.h"

extern void ssb_game_init(void),ssb_game_tick(void);
extern void nativeAssetsShutdown(void);
extern volatile uint32_t ssb_frame_count,ssb_display_lists;
uint32_t __stacksize__=512*1024;
volatile uint32_t ssb_test_buttons;
volatile int32_t ssb_test_stick_x,ssb_test_stick_y;
volatile uint32_t ssb_test_active;
/* Diagnostic taps enter the same hit test and save path as real HID input. */
volatile uint32_t native_test_touch;
volatile uint32_t native_test_cstick_active;
volatile int32_t native_test_cstick_x,native_test_cstick_y;
#ifdef SSB_RELEASE
volatile uint32_t ssb_test_frame_limit;
volatile uint32_t ssb_test_inputs;
volatile uint32_t ssb_test_logging;
volatile uint32_t ssb_test_metrics;
volatile uint32_t ssb_test_boot_gate=1;
#else
volatile uint32_t ssb_test_frame_limit=600;
volatile uint32_t ssb_test_inputs=1;
volatile uint32_t ssb_test_logging=1;
volatile uint32_t ssb_test_metrics=1;
volatile uint32_t ssb_test_boot_gate;
#endif
volatile uint32_t ssb_test_capture_audio;
volatile int32_t ssb_test_single_stage=-1;
volatile int32_t ssb_test_start_scene=-1;
static FILE* audioCapture;
static uint32_t audioCaptureBytes;
static ndspWaveBuf dspCapture;
static volatile bool dspCaptureProgress,dspCaptureDone;
static FILE* logFile;
static uint16_t buttons;
static int8_t stickX,stickY;
static bool audioReady;
static ndspWaveBuf wave[6];
static int16_t* pcm;
static unsigned waveNext;
static uint32_t audioDrops;
static uint64_t audioStart;
void nativeAudioBegin(void){audioStart=svcGetSystemTick();}
void nativeAudioEnd(void){native_perf_render.audio_ms+=(svcGetSystemTick()-audioStart)*(1000.0f/SYSCLOCK_ARM11);}
volatile uint32_t native_fps_tenths,native_fps_updates;
static uint64_t fpsWindow;
static uint32_t fpsDisplayLists;
static aptHookCookie performanceAptHook;
static void performanceAptEvent(APT_HookType hook,void* unused) {
    if(hook==APTHOOK_ONSUSPEND){nativeIoDrain();nativePerfResetClock();}
    if(hook==APTHOOK_ONRESTORE)nativePerfResetClock();
}
static void updateFps(uint64_t now) {
    uint64_t elapsed=now-fpsWindow;
    if(elapsed<SYSCLOCK_ARM11/2)return;
    /* Count presented game frames, not eyes or simulation ticks. Update only
     * twice per second and flush only the CPU-owned bottom framebuffer. */
    native_fps_tenths=((uint64_t)(ssb_display_lists-fpsDisplayLists)*10*SYSCLOCK_ARM11+elapsed/2)/elapsed;
    native_fps_updates++;
    fpsDisplayLists=ssb_display_lists;fpsWindow=now;

}
static void captureDspCallback(void* unused) {
    if(dspCapture.offset)dspCaptureProgress=true;
    else if(dspCaptureProgress){ndspSetCapture(NULL);dspCaptureDone=true;}
}
void port_log(const char*,...);
static struct TestInput {unsigned begin,end,buttons;int x,y;} testInput[128];
static unsigned testInputCount;
static bool testInputsLoaded;
static void loadTestInputs(void) {
    if(!ssb_test_inputs||testInputsLoaded)return;
    testInputsLoaded=true;
    FILE* f=fopen("sdmc:/3ds/ssb64/test-input.txt","r");if(!f)return;
    while(testInputCount<128) {
        struct TestInput* p=&testInput[testInputCount];
        if(fscanf(f,"%u %u %x %d %d",&p->begin,&p->end,&p->buttons,&p->x,&p->y)!=5)break;
        testInputCount++;
    }
    fclose(f);port_log("Loaded %u scripted input intervals\n",testInputCount);
}

void port_log(const char* fmt,...) {
    if(!logFile||!ssb_test_logging)return;
    va_list va;va_start(va,fmt);vfprintf(logFile,fmt,va);va_end(va);
    if(strstr(fmt,"FAIL")||strstr(fmt,"assert")||strstr(fmt,"Assert")||strstr(fmt,"ABORT")||strstr(fmt,"Unexpected"))fflush(logFile);
}
void port_stats(const char* fmt,...) {
    if(!logFile||!ssb_test_metrics)return;
    va_list va;va_start(va,fmt);vfprintf(logFile,fmt,va);va_end(va);
}
extern void __real_abort(void) __attribute__((noreturn));
void __wrap_abort(void) __attribute__((noreturn));
void __wrap_abort(void) {
    if(logFile){
        fprintf(logFile,"ABORT frame=%lu caller=%p\n",(unsigned long)ssb_frame_count,__builtin_return_address(0));
        fflush(logFile);
    }
    __real_abort();
}
uint64_t native_time_ticks(void) {
    uint64_t t=svcGetSystemTick();
    return (t/SYSCLOCK_ARM11)*46875000ull+(t%SYSCLOCK_ARM11)*46875000ull/SYSCLOCK_ARM11;
}
void native_read_pad(uint16_t* b,int8_t* x,int8_t* y) {
    loadTestInputs();
    *b=buttons;*x=stickX;*y=stickY;
    if(testInputCount){
        *b=0;*x=0;*y=0;
        for(unsigned i=0;i<testInputCount;i++){
            struct TestInput* p=&testInput[i];
            if(ssb_frame_count>=p->begin&&ssb_frame_count<p->end){*b=p->buttons;*x=p->x;*y=p->y;}
        }
    }
    if(ssb_test_active){*b=ssb_test_buttons;*x=ssb_test_stick_x;*y=ssb_test_stick_y;}
}
static void scanInput(void) {
    hidScanInput();uint32_t held=hidKeysHeld();circlePosition pos;hidCircleRead(&pos);
    circlePosition cstick={0};hidCstickRead(&cstick);
    if(native_test_cstick_active){cstick.dx=native_test_cstick_x;cstick.dy=native_test_cstick_y;}
    nativeControlsScan(cstick.dx,cstick.dy);
    if((hidKeysDown()&KEY_TOUCH)||native_test_touch){
        touchPosition touch;hidTouchRead(&touch);
        if(native_test_touch){touch.px=native_test_touch&65535;touch.py=native_test_touch>>16;native_test_touch=0;}
        nativeBottomTouch(touch.px,touch.py);
    }
    buttons=0;
    if(held&KEY_A)buttons|=0x8000;
    if(held&KEY_B)buttons|=0x4000;
    if(held&(KEY_ZL|KEY_ZR))buttons|=0x0010;
    if(held&KEY_START)buttons|=0x1000;
    if(held&KEY_DUP)buttons|=0x0820;
    if(held&KEY_DDOWN)buttons|=0x0400;
    if(held&KEY_DLEFT)buttons|=0x0200;
    if(held&KEY_DRIGHT)buttons|=0x0100;
    if(held&(KEY_L|KEY_R))buttons|=0x2000;
    if(held&(KEY_X|KEY_Y))buttons|=0x0008;
    int x=pos.dx*80/156,y=pos.dy*80/156;
    stickX=x>80?80:x<-80?-80:x;stickY=y>80?80:y<-80?-80:y;
}
void portAudioSubmitFrame(const void* samples,int count) {
    if(count<=0 || count>1024)abort();
    if(ssb_test_capture_audio && audioCaptureBytes<32000*4*30) {
        if(!audioCapture){
            audioCapture=fopen("sdmc:/3ds/ssb64/audio-test.wav","wb+");
            if(audioCapture){setvbuf(audioCapture,NULL,_IOFBF,65536);uint8_t header[44]={0};fwrite(header,1,44,audioCapture);}
        }
        if(audioCapture)audioCaptureBytes+=fwrite(samples,1,count*4,audioCapture);
    }
    if(!audioReady)return;
    if(ssb_test_capture_audio&&ssb_frame_count>=900&&!dspCapture.data_vaddr){
        dspCapture.nsamples=160*4096;
        dspCapture.data_vaddr=linearAlloc(dspCapture.nsamples*4);
        if(dspCapture.data_vaddr){
            memset((void*)dspCapture.data_vaddr,0,dspCapture.nsamples*4);
            ndspSetCapture(&dspCapture);ndspSetCallback(captureDspCallback,NULL);
        }
    }
    ndspWaveBuf* w=&wave[waveNext];
    if(w->status!=NDSP_WBUF_DONE && w->status!=NDSP_WBUF_FREE){audioDrops++;return;}
    memcpy((void*)w->data_vaddr,samples,count*4);
    DSP_FlushDataCache(w->data_vaddr,count*4);
    w->nsamples=count;ndspChnWaveBufAdd(0,w);
    waveNext=(waveNext+1)%6;
}
static void initAudio(void) {
    Result rc=ndspInit();
    port_log("ndspInit=%08lx\n",(unsigned long)rc);
    if(R_FAILED(rc))return;
    pcm=linearAlloc(6*1024*4);
    if(!pcm){ndspExit();return;}
    ndspSetOutputMode(NDSP_OUTPUT_STEREO);
    ndspChnSetInterp(0,NDSP_INTERP_POLYPHASE);
    ndspChnSetRate(0,32000);
    ndspChnSetFormat(0,NDSP_FORMAT_STEREO_PCM16);
    float mix[12]={1,1};ndspChnSetMix(0,mix);
    for(unsigned i=0;i<6;i++)wave[i].data_vaddr=pcm+i*2048;
    audioReady=true;
}
static uint8_t saveBytes[32768];
static bool saveLoaded;
static void loadSave(void) {
    if(saveLoaded)return;
    const char* paths[]={"sdmc:/3ds/ssb64/save.bin","sdmc:/3ds/ssb64/save.bak","romfs:/initial-save.bin"};
    bool loaded=false;
    for(unsigned i=0;i<3&&!loaded;i++){
        FILE* f=fopen(paths[i],"rb");if(!f)continue;
        loaded=fread(saveBytes,1,sizeof(saveBytes),f)==sizeof(saveBytes)&&fgetc(f)==EOF;
        fclose(f);
        if(loaded)port_log("SAVE loaded %s\n",paths[i]);
    }
    if(!loaded)memset(saveBytes,0,sizeof(saveBytes));
    saveLoaded=true;
}
int port_save_read(uintptr_t offset,void* dst,size_t size) {
    loadSave();if(offset>sizeof(saveBytes)||size>sizeof(saveBytes)-offset)return -1;
    memcpy(dst,saveBytes+offset,size);return 0;
}
static void writeSave(const void* data){
    FILE* f=fopen("sdmc:/3ds/ssb64/save.tmp","wb");if(!f)goto failed;
    bool ok=fwrite(data,1,sizeof(saveBytes),f)==sizeof(saveBytes);
    if(fflush(f))ok=false;if(fclose(f))ok=false;
    if(!ok)goto failed;
    /* FAT rename does not necessarily replace an existing destination.
     * Keep a recoverable previous copy across interruption or a failed rename. */
    const char* current="sdmc:/3ds/ssb64/save.bin";
    const char* backup="sdmc:/3ds/ssb64/save.bak";
    if(remove(backup)!=0&&errno!=ENOENT)goto failed;
    bool hadPrevious=rename(current,backup)==0;
    if(!hadPrevious&&errno!=ENOENT)goto failed;
    if(rename("sdmc:/3ds/ssb64/save.tmp",current)!=0){
        if(hadPrevious)rename(backup,current);
        goto failed;
    }
    return;
failed: __atomic_fetch_add(&native_perf_error,1,__ATOMIC_RELAXED);
}
int port_save_write(uintptr_t offset,const void* src,size_t size){
    loadSave();if(offset>sizeof(saveBytes)||size>sizeof(saveBytes)-offset)return -1;
    if(!memcmp(saveBytes+offset,src,size))return 0;
    memcpy(saveBytes+offset,src,size);
    return nativeIoSubmit(writeSave,saveBytes,sizeof(saveBytes),2);
}
int main(void) {
    /* Diagnostic binaries wait for the harness to finish setting startup
     * options. The installable build starts immediately without a debugger. */
    while(!ssb_test_boot_gate)svcSleepThread(1000000);
    gfxInitDefault();consoleInit(GFX_BOTTOM,NULL);
    Result rc=romfsInit();
    mkdir("sdmc:/3ds",0777);mkdir("sdmc:/3ds/ssb64",0777);
    nativeDisplayLoad();
    nativeControlsLoad();
    if(nativeIoInit())native_perf_error++;
    logFile=fopen("sdmc:/3ds/ssb64/game.log","w");
    if(logFile)setvbuf(logFile,NULL,_IOFBF,65536);
    nativeBottomInit();
    port_log("Native ARM11 startup, romfs=%08lx\n",(unsigned long)rc);
    extern u32 __ctru_heap_size,__ctru_linear_heap_size;
    port_log("MEMORY heap=%u linear=%u linear_free=%u\n",__ctru_heap_size,__ctru_linear_heap_size,linearSpaceFree());
    if(R_FAILED(rc))return 2;
    osSetSpeedupEnable(true);initAudio();loadTestInputs();
#ifdef SSB_RELEASE
    /* A persistent bottom-screen warning appears if DSP initialization failed. */
#endif
    if(ssb_test_single_stage>=0&&ssb_test_single_stage<18){
        char stage[12];snprintf(stage,sizeof(stage),"%ld",(long)ssb_test_single_stage);
        int envResult=setenv("SSB64_SPGAME_STAGE",stage,1);
        port_log("TEST_STAGE requested=%ld setenv=%d\n",(long)ssb_test_single_stage,envResult);
    }
    if(ssb_test_start_scene>=0&&ssb_test_start_scene<=61){
        char scene[12];snprintf(scene,sizeof(scene),"%ld",(long)ssb_test_start_scene);
        setenv("SSB64_START_SCENE",scene,1);
    }
    nativePerfInit();aptHook(&performanceAptHook,performanceAptEvent,NULL);
    ssb_game_init();
    uint64_t frameWindow=svcGetSystemTick(),frameWork=0;
    fpsWindow=frameWindow;fpsDisplayLists=ssb_display_lists;
    while(aptMainLoop()) {
        scanInput();if(hidKeysDown()&KEY_SELECT)break;
        unsigned previousLists=ssb_display_lists;
        native_perf_render.audio_ms=0;
        native_perf_render.render_total_ms=0;
        native_asset_reads=native_asset_hits=native_asset_bytes=0;
        uint64_t startTick=svcGetSystemTick();ssb_game_tick();
        uint64_t endTick=svcGetSystemTick();
        updateFps(endTick);
        nativeBottomFrame(native_fps_tenths,audioReady);
        endTick=svcGetSystemTick();frameWork+=endTick-startTick;
        nativePerfTick(endTick,endTick-startTick,ssb_display_lists,audioDrops);
        if(ssb_frame_count%60==0){

            port_stats("TICK frame=%lu dl=%lu audio_drops=%lu\n",ssb_frame_count,ssb_display_lists,audioDrops);
            uint64_t now=svcGetSystemTick();
            port_stats("PACE frame=%u fps=%.2f tick_ms=%.3f\n",ssb_frame_count,
                60.0*SYSCLOCK_ARM11/(now-frameWindow),1000.0*frameWork/(60.0*SYSCLOCK_ARM11));
            port_stats("DETAIL frame=%u scene=%u wait_ms=%.3f replay_ms=%.3f render_ms=%.3f audio_ms=%.3f draws=%u binds=%u fog=%u cmd=%u\n",
                ssb_frame_count,native_perf_game.scene,native_perf_render.wait_ms,native_perf_render.replay_ms,
                native_perf_render.render_total_ms,native_perf_render.audio_ms,native_perf_render.draw_calls,
                native_perf_render.texture_binds,native_perf_render.fog_uploads,native_perf_render.command_bytes);
            frameWindow=now;frameWork=0;
            if(ssb_test_metrics&&ssb_frame_count%600==0){
                struct mallinfo memory=mallinfo();
                port_stats("MEMORY frame=%u allocated=%u free_blocks=%u arena=%u linear_free=%u\n",
                    ssb_frame_count,memory.uordblks,memory.fordblks,memory.arena,linearSpaceFree());
            }
            if(logFile)fflush(logFile);
        }
        if(ssb_test_frame_limit && ssb_frame_count>=ssb_test_frame_limit)break;
#ifdef SSB_GRAPHICS
        if(ssb_display_lists==previousLists)gspWaitForVBlank();
#else
        gspWaitForVBlank();
#endif
    }
    nativePerfFinish("app_exit");nativeIoExit();aptUnhook(&performanceAptHook);nativeBottomExit();
    if(audioCapture){
        uint32_t header[]={0x46464952,audioCaptureBytes+36,0x45564157,0x20746d66,16,
            0x00020001,32000,128000,0x00100004,0x61746164,audioCaptureBytes};
        fseek(audioCapture,0,SEEK_SET);fwrite(header,1,sizeof(header),audioCapture);fclose(audioCapture);
    }
    if(audioReady){
        ndspSetCapture(NULL);ndspSetCallback(NULL,NULL);
        port_stats("DSP frames=%u dropped_frames=%u captured_samples=%u\n",ndspGetFrameCount(),ndspGetDroppedFrames(),dspCaptureDone?dspCapture.nsamples:dspCapture.offset);
        ndspChnWaveBufClear(0);ndspExit();linearFree(pcm);
    }
    if(dspCapture.data_vaddr){
        uint32_t bytes=(dspCaptureDone?dspCapture.nsamples:dspCapture.offset)*4;
        uint32_t rate=(uint32_t)NDSP_SAMPLE_RATE;
        uint32_t header[]={0x46464952,bytes+36,0x45564157,0x20746d66,16,0x00020001,rate,rate*4,0x00100004,0x61746164,bytes};
        FILE* f=fopen("sdmc:/3ds/ssb64/audio-dsp-test.wav","wb");
        if(f){fwrite(header,1,sizeof(header),f);fwrite(dspCapture.data_vaddr,1,bytes,f);fclose(f);}
        linearFree((void*)dspCapture.data_vaddr);
    }
    #ifdef SSB_GRAPHICS
    extern void nativeRenderShutdown(void);
    nativeRenderShutdown();
    #endif
    nativeAssetsShutdown();
    port_stats("EXIT frames=%lu dl=%lu\n",ssb_frame_count,ssb_display_lists);
    if(logFile){fclose(logFile);logFile=NULL;}
    romfsExit();gfxExit();return 0;
}

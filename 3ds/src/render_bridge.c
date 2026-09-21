#include <ssb_types.h>
#include <PR/gbi.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "gfx_pc.h"
#include "rsp_platform.h"
extern void* portRelocTryResolvePointer(uint32_t);
extern bool portRelocFindContainingFile(const void*,uintptr_t*,size_t*);
extern void port_log(const char*,...);
extern void nativeRenderInit(void);
extern void nativeRenderBegin(void);
extern void nativeRenderCapture(void);
extern char __text_start,__end__;
void* native_current_dl;
unsigned native_stereo_backdrop;
static uintptr_t segments[16];
static unsigned dlDepth,dlCommands;
static struct Range {uintptr_t begin,end;} ranges[4096];
static unsigned rangeCount;
static struct Range cached;
/* Runtime endian conversion is idempotent per asset allocation. Keep exact
 * requests cached, and invalidate on the same events as the upstream tracker. */
static struct Fixup {const void* address;unsigned count,epoch;} fixed[2][4096];
static unsigned fixupEpoch=1;
volatile uint32_t native_test_dump_textures;
void nativeDumpTexture(const uint8_t* pixels,unsigned w,unsigned h,const void* address,unsigned fmt,unsigned siz,unsigned line,unsigned masks,unsigned shifts){
    extern volatile uint32_t ssb_frame_count;
    static unsigned count;
    if(!native_test_dump_textures||ssb_frame_count!=850||count>=256)return;
    char path[128];snprintf(path,sizeof(path),"sdmc:/3ds/ssb64/texture-%03u.ppm",count);
    FILE* f=fopen(path,"wb");if(!f)return;
    fprintf(f,"P6\n%u %u\n255\n",w,h);
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++)fwrite(pixels+(y*w+x)*4,1,3,f);
    fclose(f);
    snprintf(path,sizeof(path),"sdmc:/3ds/ssb64/texture-%03u.rgba",count);
    f=fopen(path,"wb");if(f){fwrite(pixels,4,w*h,f);fclose(f);}
    port_log("TEXTURE id=%u addr=%p size=%ux%u fmt=%u siz=%u line=%u masks=%04x shifts=%04x\n",count++,address,w,h,fmt,siz,line,masks,shifts);
}
static void invalidateFixups(void){
    if(++fixupEpoch==0){memset(fixed,0,sizeof(fixed));fixupEpoch=1;}
}
extern void __real_portResetStructFixups(void);
extern void __real_portEvictStructFixupsInRange(const void*,size_t);
void __wrap_portResetStructFixups(void){invalidateFixups();__real_portResetStructFixups();}
void __wrap_portEvictStructFixupsInRange(const void* p,size_t n){invalidateFixups();__real_portEvictStructFixupsInRange(p,n);}
static void fixAsset(const void* p,unsigned count,unsigned kind){
    unsigned hash=(((uintptr_t)p>>4)^(count*2654435761u))&4095;
    struct Fixup* f=&fixed[kind][hash];
    if(f->epoch==fixupEpoch&&f->address==p&&f->count==count)return;
    if(kind)portRelocFixupVertexAtRuntime(p,count);else portRelocFixupTextureAtRuntime(p,count);
    uintptr_t base;size_t size;
    if(portRelocFindContainingFile(p,&base,&size))*f=(struct Fixup){p,count,fixupEpoch};
}
void nativeFixVertices(const void* p,unsigned n){fixAsset(p,n,1);}
void nativeFixTexture(const void* p,unsigned n){fixAsset(p,n,0);}
void port_dl_range_register(const void*p,size_t n,const char*l) {
    uintptr_t lo=(uintptr_t)p;
    if(!p||!n||lo+n<lo)return;
    cached.begin=cached.end=0;
    for(unsigned i=0;i<rangeCount;i++)if(ranges[i].begin==lo){ranges[i].end=lo+n;return;}
    if(rangeCount==4096)abort();
    ranges[rangeCount++]=(struct Range){lo,lo+n};
}
void port_dl_range_unregister(const void*p) {
    cached.begin=cached.end=0;
    for(unsigned i=0;i<rangeCount;i++)if(ranges[i].begin==(uintptr_t)p){ranges[i]=ranges[--rangeCount];return;}
}
int port_dl_check_addr(uintptr_t p) {
    if(p>=cached.begin&&p+8<=cached.end)return 1;
    for(unsigned i=0;i<rangeCount;i++)if(p>=ranges[i].begin&&p+8<=ranges[i].end){cached=ranges[i];return 1;}
    return 0;
}
static void fail(const char* why,uintptr_t value,const void* cmd) {
    port_log("GFX FAILURE %s value=%08lx command=%p depth=%u count=%u\n",why,(unsigned long)value,cmd,dlDepth,dlCommands);abort();
}
void* nativeResolveGfxAddress(uintptr_t word,const void* command,bool branch) {
    if(!word)return NULL;
    void* ptr=portRelocTryResolvePointer(word);
    if(ptr)return ptr;
    unsigned segment=word>>24;uintptr_t offset=word&0xffffff;
    if(segment==0x0e) {
        if(branch&&segments[segment])return (void*)(segments[segment]+offset);
        uintptr_t base=0;size_t size=0;
        if(portRelocFindContainingFile(command,&base,&size)&&offset<size)return (void*)(base+offset);
    }
    if(segment<16&&segments[segment]&&segment!=8)return (void*)(segments[segment]+offset);
    return (void*)word;
}
void nativeSetSegment(unsigned segment,uintptr_t base) {
    if(segment>=16)fail("segment",segment,native_current_dl);
    void* p=portRelocTryResolvePointer(base);
    segments[segment]=p?(uintptr_t)p:base;
}
void nativeDlFrameBegin(void) {
    dlDepth=dlCommands=0;native_stereo_backdrop=0;
    extern volatile uint32_t ssb_frame_count;
    extern void portTextureCacheDeleteRange(const void*,size_t);
    if(native_test_dump_textures&&ssb_frame_count==850)portTextureCacheDeleteRange(NULL,0xffffffffu);
}
void native_dl_enter(void) {if(++dlDepth>64)fail("DL recursion",dlDepth,native_current_dl);}
void native_dl_leave(void) {dlDepth--;}
void native_dl_check(const void*p) {
    if(++dlCommands>500000 || !port_dl_check_addr((uintptr_t)p))fail("DL bounds",(uintptr_t)p,p);
}
void nativeUnknownOpcode(unsigned opcode,const void*p) {fail("unsupported opcode",opcode,p);}
void nativeRenderAssertion(const char* expression,int line,const void* p) {port_log("Renderer assertion line=%d expression=%s\n",line,expression);fail("assert",line,p);}
void nativeCombineTrace(uint32_t a,uint32_t b,uint32_t l,uint32_t h){
    extern volatile uint32_t ssb_test_logging;
    if(!ssb_test_logging)return;
    static uint32_t seen[256][4];static unsigned count;
    for(unsigned i=0;i<count;i++)if(seen[i][0]==a&&seen[i][1]==b&&seen[i][2]==l&&seen[i][3]==h)return;
    if(count==256)return;
    seen[count][0]=a;seen[count][1]=b;seen[count][2]=l;seen[count++][3]=h;
    port_log("COMBINE %08x %08x %08x %08x\n",a,b,l,h);
}
void nativeTextureLoadDiagnostic(unsigned tile,unsigned slot,unsigned bits,unsigned x,unsigned y,unsigned w,unsigned h,unsigned stride,unsigned bytes,unsigned pitch){port_log("TILE tile=%u slot=%u bits=%u origin=%u,%u size=%u,%u stride=%u bytes=%u pitch=%u\n",tile,slot,bits,x,y,w,h,stride,bytes,pitch);}
void native_submit_display_list(void* dl) {
    static int initialized;
    if(!initialized){port_dl_range_register(&__text_start,(uintptr_t)&__end__-(uintptr_t)&__text_start,"native image");nativeRenderInit();initialized=1;}
    nativeRenderBegin();gfx_start_frame();gfx_run(dl);gfx_end_frame();nativeRenderCapture();
}
void portResetPackedDisplayListCache(void) {} /* ARM32 Gfx and ROM commands both occupy eight bytes. */
void portPackedDisplayListCacheDeleteRange(const void*p,size_t n) {}
uint32_t native_game_width=320,native_game_height=240;
void GfxSetNativeDimensions(uint32_t w,uint32_t h) {
    if(!((w==320&&h==240)||(w==640&&h==480)))fail("game dimensions",w,0);
    native_game_width=w;native_game_height=h;
}
void GfxSetTight4_3ScissorWindow(int enabled) {}
void GfxSetWidescreenFramebufferPersistence(int enabled) {}
int port_capture_register_fb_for_subrect(const void*p,unsigned n,float x,float y,float w,float h) {
    extern int nativeReadbackPhoto(void*,unsigned,float,float,float,float);
    extern void portTextureCacheDeleteRange(const void*,size_t);
    /* Mark any ROM texture words converted before replacing them with pixels. */
    nativeFixTexture(p,n);
    int result=nativeReadbackPhoto((void*)p,n,x,y,w,h);
    if(!result)portTextureCacheDeleteRange(p,n);
    return result;
}
void port_capture_release_all(void) {}
void portDiagArmImportCapture(int n) {}

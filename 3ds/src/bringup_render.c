/* Linkable runtime probe only. This file MUST NOT enter a playable package. */
#ifndef SSB_BRINGUP
#error Bring-up renderer cannot be used in a release build
#endif
#include <stdint.h>
#include <stddef.h>
volatile uintptr_t ssb_probe_display_list;
void native_submit_display_list(void* dl) {ssb_probe_display_list=(uintptr_t)dl;}
void port_dl_range_register(const void*p,size_t n,const char*l) {}
void port_dl_range_unregister(const void*p) {}
int port_dl_check_addr(uintptr_t p) {return p>=0x08000000&&p<0x10000000;}
void portResetPackedDisplayListCache(void) {}
void portPackedDisplayListCacheDeleteRange(const void*p,size_t n) {}
void portTextureCacheDeleteRange(const void*p,size_t n) {}
void GfxSetNativeDimensions(uint32_t w,uint32_t h) {}
void GfxSetTight4_3ScissorWindow(int enabled) {}
void GfxSetWidescreenFramebufferPersistence(int enabled) {}
int port_capture_register_fb_for_subrect(const void*p,unsigned n,float x,float y,float w,float h) {return -1;}
void port_capture_release_all(void) {}
void portDiagArmImportCapture(int n) {}

#pragma once
void port_log(const char*,...);
void port_stats(const char*,...);
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "native_stereo.h"
#include "native_display.h"
#include "native_perf.h"
extern volatile uint32_t native_test_dump_textures,ssb_frame_count;
extern unsigned native_depth_mask,native_stencil_ref,native_alpha_threshold;
enum {iodNormal,iodGoddard,iodFileSelect,iodStarSelect,iodCannon};
extern void* native_current_dl;
extern bool gGfx3DEnabled;
extern int native_stereo_perspective;
extern float native_stereo_focus_w,gSliderLevel;
extern int native_fog_primitive;
int nativeStereoLoadProjection(const void* matrix);
int memcmp(const void*,const void*,size_t);
void* nativeResolveGfxAddress(uintptr_t word,const void* command,bool branch);
void nativeSetSegment(unsigned segment,uintptr_t base);
void nativeDlFrameBegin(void);
void native_dl_enter(void);
void native_dl_leave(void);
void native_dl_check(const void* command);
void nativeUnknownOpcode(unsigned opcode,const void* command);
void nativeRenderAssertion(const char*,int,const void*);
void nativeCombineTrace(uint32_t,uint32_t,uint32_t,uint32_t);
void nativeTextureLoadDiagnostic(unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned,unsigned);
void portRelocFixupVertexAtRuntime(const void*,unsigned);
void portRelocFixupTextureAtRuntime(const void*,unsigned);
void nativeFixTexture(const void*,unsigned);
void nativeFixVertices(const void*,unsigned);
int nativeTextureAlive(unsigned);
void nativeTextureTouch(unsigned);
extern int native_second_needs_shade;
extern int native_texture_clamp_s,native_texture_clamp_t;
void nativeDumpTexture(const uint8_t*,unsigned,unsigned,const void*,unsigned,unsigned,unsigned,unsigned,unsigned);
void nativeSetSecondCycle(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);

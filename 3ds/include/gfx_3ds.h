#pragma once
#include <3ds.h>
#include <citro3d.h>
#include <math.h>
#include <stdlib.h>
#include "native_stereo.h"
#include "native_display.h"
#define __3ds_u32 u32
#define VERTEX_SHADER_SIZE 12
#define G_TX_CLAMP 2
#define G_TX_MIRROR 1
typedef enum {GFX_3DS_MODE_NORMAL,GFX_3DS_MODE_WIDE,GFX_3DS_MODE_AA_22,GFX_3DS_MODE_WIDE_AA_12} Gfx3DSMode;
extern Gfx3DSMode gGfx3DSMode;
extern C3D_RenderTarget *gTarget,*gTargetRight;
extern float gSliderLevel;
extern bool gGfx3DEnabled;
extern int uLoc_projection,uLoc_modelView;
extern int uLoc_eye;
extern float native_stereo_focus_w;
void port_log(const char*,...);
void port_stats(const char*,...);

#pragma once
#include <stdint.h>
#include <math.h>
extern volatile uint32_t native_widescreen;
void nativeDisplayLoad(void);
int nativeDisplayToggle(void);
static inline float nativeDisplayClipScale(void){return native_widescreen?(9.0f/11.0f):1.0f;}
/* The N64 game's visible canvas is [10,310] x [10,230]. Fill 320x240
 * in 4:3 and 400x240 in wide. The projection compensates for both the
 * removed overscan and the wider viewport: equal world units have equal
 * physical size in both modes and the wide camera sees 25% more horizontally.
 * Uniform 4:3 scaling crops 3.33 original pixels at each side of the safe
 * canvas; projected sprites and geometry therefore share exactly one scale.
 * Frontend coordinates are always normalized to 320x240, including credits. */
static inline float nativeDisplayX(float x){return (x-160)*(native_widescreen?(400.0f/300):(240.0f/220))+200;}
static inline float nativeDisplayY(float y){return (y-10)*(240.0f/220);}
static inline int nativeDisplayClamp(int x,int limit){return x<0?0:x>limit?limit:x;}
/* Clip the hardware viewport to legal positive LCD coordinates, compensating
 * in the existing projection uniform. This retains partially visible quads
 * and magnifier viewports without an intermediate framebuffer or extra pass.
 * adj = X scale, Y scale, X translation, Y translation before LCD rotation. */
static inline int nativeDisplayViewport(int x,int y,int w,int h,int* vp,float* adj){
    float l=nativeDisplayX(x),b=nativeDisplayY(y);
    float r=nativeDisplayX(x+w),t=nativeDisplayY(y+h);
    int il=nativeDisplayClamp((int)lroundf(l),400),ir=nativeDisplayClamp((int)lroundf(r),400);
    int ib=nativeDisplayClamp((int)lroundf(b),240),it=nativeDisplayClamp((int)lroundf(t),240);
    if(!native_widescreen){if(il<40)il=40;if(ir>360)ir=360;}
    if(ir<=il||it<=ib)return 0;
    vp[0]=ib;vp[1]=400-ir;vp[2]=it-ib;vp[3]=ir-il;
    adj[0]=(r-l)/(ir-il);adj[1]=(t-b)/(it-ib);
    adj[2]=(l+r-il-ir)/(ir-il);adj[3]=(b+t-ib-it)/(it-ib);
    return 1;
}

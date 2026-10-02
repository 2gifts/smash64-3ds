#include "native_controls.h"
#include <math.h>
unsigned native_cstick_direction,native_cstick_jump_guard;
void nativeControlsScan(int x,int y){
    static unsigned armed;
    native_cstick_direction=native_cstick_jump_guard=0;
    if(!native_cstick_enabled){armed=0;return;}
    int ax=x<0?-x:x,ay=y<0?-y:y;
    /* Hysteresis rejects nub noise. Enabling while held requires returning
     * to center, as does changing direction without releasing the nub. */
    if(ax<24&&ay<24){armed=1;return;}
    if(!armed||(ax<40&&ay<40))return;
    armed=0;
    native_cstick_direction=ax>=ay?(x>0?CSTICK_RIGHT:CSTICK_LEFT):(y>0?CSTICK_UP:CSTICK_DOWN);
}
/* The circle pad rests a few units off center and wanders a little, which
 * the original 1:1 scaling passed through as a slow drift (most visible as
 * a creeping menu cursor). A small radial deadzone removes it; the rest of
 * the range is rescaled so full tilt and walk/run thresholds are unchanged. */
void nativeStickFromCirclePad(int dx,int dy,int8_t* x,int8_t* y){
    float r=sqrtf((float)(dx*dx+dy*dy));
    if(r<=CIRCLE_PAD_DEADZONE){*x=*y=0;return;}
    float scale=(r-CIRCLE_PAD_DEADZONE)/(CIRCLE_PAD_FULL-CIRCLE_PAD_DEADZONE)*80.0f/r;
    int sx=(int)lroundf(dx*scale),sy=(int)lroundf(dy*scale);
    *x=sx>80?80:sx<-80?-80:sx;*y=sy>80?80:sy<-80?-80:sy;
}

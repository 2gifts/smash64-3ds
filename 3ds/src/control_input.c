#include "native_controls.h"
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

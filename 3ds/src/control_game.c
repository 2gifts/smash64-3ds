#include <ft/fighter.h>
#include <sc/scene.h>
#include "native_controls.h"
static int localHuman(FTStruct* fp){return fp->pkind==nFTPlayerKindMan&&fp->input.controller==&gSYControllerDevices[0];}
int port_enhancement_tap_jump_disabled(int player){
    if((unsigned)player>=4||!gSCManagerBattleState)return 0;
    GObj* g=gSCManagerBattleState->players[player].fighter_gobj;
    return g&&localHuman(ftGetStruct(g))&&(native_tap_jump_disabled||native_cstick_jump_guard);
}
void nativeControlsApplyFighter(void* fighter){
    FTStruct* fp=ftGetStruct((GObj*)fighter);
    static unsigned pending,scene=~0u;
    unsigned current=gSCManagerSceneData.scene_curr;
    if(!localHuman(fp))return;
    if(scene!=current){pending=0;scene=current;}
    if(!native_cstick_enabled||fp->is_control_disable||gSCManagerBattleState->game_status!=1){pending=0;return;}
    if(native_cstick_direction)pending=native_cstick_direction;
    if(!pending)return;
    /* Apply after the engine samples normal inputs, so holding A or the
     * Circle Pad cannot turn this into a tilt. All attack eligibility and
     * move selection still run through the original fighter interrupts. */
    fp->input.pl.stick_range.x=pending==CSTICK_RIGHT?80:pending==CSTICK_LEFT?-80:0;
    fp->input.pl.stick_range.y=pending==CSTICK_UP?80:pending==CSTICK_DOWN?-80:0;
    fp->tap_stick_x=fp->tap_stick_y=1;
    fp->input.pl.button_hold|=fp->input.button_mask_a;
    fp->input.pl.button_tap|=fp->input.button_mask_a;
    native_cstick_jump_guard=pending==CSTICK_UP;
    /* Preserve direction during the original hitlag input buffer only. */
    if(!fp->hitlag_tics)pending=0;
}

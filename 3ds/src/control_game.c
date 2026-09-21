#include <ft/fighter.h>
#include <sc/scene.h>
#include "native_controls.h"
static FTStruct* cstickFighter;
static unsigned cstickAttack;
static int localHuman(FTStruct* fp){return fp->pkind==nFTPlayerKindMan&&fp->input.controller==&gSYControllerDevices[0];}
extern sb32 __real_ftCommonAttackLw4CheckInterruptSquat(GObj*);
sb32 __wrap_ftCommonAttackLw4CheckInterruptSquat(GObj* fighter){
    /* The original crouch interrupt requires an animation flag in addition
     * to a fresh downward flick. A C-stick flick is an explicit smash even
     * after the Circle Pad has held crouch past that animation window. Keep
     * the ordinary eligibility/item checks and never alter crouch's union. */
    FTStruct* fp=ftGetStruct(fighter);
    if(native_cstick_enabled&&localHuman(fp)&&fp==cstickFighter&&cstickAttack==CSTICK_DOWN)
        return ftCommonAttackLw4CheckInterruptCommon(fighter);
    return __real_ftCommonAttackLw4CheckInterruptSquat(fighter);
}
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
    cstickFighter=NULL;cstickAttack=0;
    if(scene!=current){pending=0;scene=current;}
    if(!native_cstick_enabled||fp->is_control_disable||gSCManagerBattleState->game_status!=1){pending=0;return;}
    if(native_cstick_direction)pending=native_cstick_direction;
    if(!pending)return;
    cstickFighter=fp;cstickAttack=pending;
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

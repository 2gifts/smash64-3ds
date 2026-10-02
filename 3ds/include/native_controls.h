#pragma once
#include <stdint.h>
enum {CSTICK_NONE,CSTICK_RIGHT,CSTICK_LEFT,CSTICK_UP,CSTICK_DOWN};
extern uint32_t native_tap_jump_disabled,native_cstick_enabled;
extern unsigned native_cstick_direction,native_cstick_jump_guard;
void nativeControlsLoad(void);
int nativeControlsToggle(unsigned option);
void nativeControlsScan(int x,int y);
/* Raw circle pad units: about 156 at full tilt, a few at rest. */
#define CIRCLE_PAD_DEADZONE 14.0f
#define CIRCLE_PAD_FULL 156.0f
void nativeStickFromCirclePad(int dx,int dy,int8_t* x,int8_t* y);
void nativeControlsApplyFighter(void* fighter);

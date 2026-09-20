#pragma once
#include <stdint.h>
enum {CSTICK_NONE,CSTICK_RIGHT,CSTICK_LEFT,CSTICK_UP,CSTICK_DOWN};
extern uint32_t native_tap_jump_disabled,native_cstick_enabled;
extern unsigned native_cstick_direction,native_cstick_jump_guard;
void nativeControlsLoad(void);
int nativeControlsToggle(unsigned option);
void nativeControlsScan(int x,int y);
void nativeControlsApplyFighter(void* fighter);

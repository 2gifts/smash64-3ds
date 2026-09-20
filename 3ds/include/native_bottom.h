#pragma once
#include <stdint.h>
/* Fixed-width snapshot shared across SDK/game translation units. No pointers
 * or engine objects survive a scene transition in the bottom-screen UI. */
typedef struct NativeBottomPlayer {
    uint32_t kind,character,costume,color,damage,stocks,level,ready,place,stock_limited;
    int32_t kos,falls,score;
    uint32_t combo_hits,combo_active;
} NativeBottomPlayer;
typedef struct NativeBottomState {
    uint32_t scene,page,stage,status,stock_mode,teams,seconds,timer,rule_stocks,rule_minutes,training,bonus,sudden_death;
    NativeBottomPlayer players[4];
} NativeBottomState;
enum {BOTTOM_MENU,BOTTOM_SELECT,BOTTOM_BATTLE,BOTTOM_RESULTS,BOTTOM_STAGE};
enum {BOTTOM_NONE,BOTTOM_PERFORMANCE,BOTTOM_DISPLAY,BOTTOM_CONTROLS,BOTTOM_GUIDE,BOTTOM_TAP_JUMP,BOTTOM_CSTICK};
void nativeBottomSnapshot(NativeBottomState*);
int nativeBottomArtInit(const char*);
void nativeBottomArtExit(void);
void nativeBottomDraw(uint16_t*,const NativeBottomState*,unsigned fps,unsigned wide,unsigned page,unsigned reports,unsigned errors,unsigned audio);
unsigned nativeBottomHit(unsigned,unsigned);
unsigned nativeBottomControlsHit(unsigned,unsigned);
void nativeBottomInit(void);
void nativeBottomTouch(unsigned,unsigned);
void nativeBottomFrame(unsigned,unsigned);
void nativeBottomExit(void);
extern uint16_t native_bottom_pixels[320*240];
extern NativeBottomState native_bottom_observed;
extern uint32_t native_bottom_redraws,native_bottom_page;
extern float native_bottom_last_ms;
extern volatile uint32_t native_test_bottom_disabled;

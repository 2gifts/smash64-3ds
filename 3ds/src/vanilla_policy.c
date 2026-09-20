/* Unrelated PC-port enhancements retain vanilla behavior. Display options and
 * the optional New 3DS controls are implemented in their own platform modules. */
#include "enhancements/enhancements.h"
#include <stdint.h>
#include <stdbool.h>
#include "native_display.h"
#define INIT_EVENT_IDS
#include "hooks/Events.h"

void EventSystemCallEvent(EventID id,void* ev,const char* f,int l,const char* key) {}
#define OFF(name) int name(void) {return 0;}
OFF(port_cheat_unlock_all)
OFF(port_cheat_unlock_luigi)
OFF(port_cheat_unlock_ness)
OFF(port_cheat_unlock_captain)
OFF(port_cheat_unlock_purin)
OFF(port_cheat_unlock_inishie)
OFF(port_cheat_unlock_soundtest)
OFF(port_cheat_unlock_itemswitch)
OFF(port_get_comp_ruleset)
OFF(port_enhancement_neutral_spawns)
OFF(port_enhancement_IsAutoZCancelEnabled)
OFF(port_enhancement_IsFailedZCancelFlashEnabled)
OFF(port_enhancement_boot_to_vs_css)
OFF(port_enhancement_skip_results_screen)
OFF(port_enhancement_cpu_level_9)
OFF(port_enhancement_classic_coop)
OFF(port_classic_coop_context)
OFF(port_classic_coop_friendly_fire)
OFF(port_enhancement_bonus_stages_enabled)
/* This hook returns a track ID, not an enable flag. Preserve every original
 * request when shuffle is disabled (track zero is Dream Land). */
extern void port_stats(const char*,...);
uint32_t port_enhancement_shuffle_music(uint32_t requested_bgm) {
    port_stats("MUSIC requested=%u selected=%u\n",requested_bgm,requested_bgm);
    return requested_bgm;
}
bool port_enhancement_is_hud_disabled(void) {return false;}
int port_enhancement_hitbox_display_override(int mode) {return mode;}
void port_classic_coop_set_context(int active) {}
void port_enhancement_analog_remap(int p,signed char*x,signed char*y) {}
void port_enhancement_c_stick_smash(int p,unsigned short*h,unsigned short*t,signed char*x,signed char*y,unsigned short pre) {}
void port_enhancement_dpad_jump(int p,unsigned short*h,unsigned short*t,unsigned short pre) {}
void port_enhancement_music_select_reset(void) {}
int port_enhancement_music_select_handle_a(uint32_t bgm) {return 0;}
int port_enhancement_music_select_handle_b(void) {return 0;}
float port_get_master_volume(void) {return 1.0f;}
float port_get_music_volume(void) {return 1.0f;}
float port_get_voice_volume(void) {return 1.0f;}
float port_get_sfx_volume(void) {return 1.0f;}
float port_widescreen_clip_x_scale(void) {return nativeDisplayClipScale();}
/* These are assets for the PC port's extra-stage pages. Vanilla stage assets
 * use the original loader when these return NULL. */
void* portCSSGetStageIconSprite(int kind) {return 0;}
void* portCSSGetStageBackgroundSprite(int kind) {return 0;}
void* portCSSGetStageNameSprite(int kind) {return 0;}
void* portCSSGetScrollArrowSprite(void) {return 0;}
void* portCSSGetScrollArrowLeftSprite(void) {return 0;}

/* Optional desktop audio command tracing is disabled in the device build. */
void acmd_trace_init(void) {}
extern void nativeAudioBegin(void),nativeAudioEnd(void);
void acmd_trace_begin_task(void) {nativeAudioBegin();}
void acmd_trace_end_task(void) {nativeAudioEnd();}
void acmd_trace_log_cmd(uint32_t a,uint32_t b) {}

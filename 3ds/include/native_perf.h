#pragma once
#include <stdint.h>
/* Shared by game and SDK translation units; no enum/bool ABI dependencies. */
typedef struct NativePerfGame {
    uint32_t scene,stage,status,game_frame,in_match;
    uint32_t fighter[4],kind[4];
} NativePerfGame;
typedef struct NativePerfRender {
    uint32_t batches,vertices,texture_hits,texture_misses,upload_bytes,eyes;
    float submit_ms,gpu_previous_ms,slider;
    float wait_ms,replay_ms,render_total_ms,audio_ms;
    uint32_t draw_calls,texture_binds,fog_uploads,command_bytes;
    float bottom_ms;
} NativePerfRender;
extern NativePerfGame native_perf_game;
extern NativePerfRender native_perf_render;
void nativePerfInit(void);
void nativePerfTick(uint64_t,uint64_t,uint32_t,uint32_t);
void nativePerfFinish(const char*);
void nativePerfResetClock(void);
extern uint32_t native_perf_saved,native_perf_error;
#ifdef __cplusplus
extern "C" {
#endif
extern uint32_t native_asset_reads,native_asset_hits,native_asset_bytes;
#ifdef __cplusplus
}
#endif

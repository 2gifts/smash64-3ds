#pragma once
#include <stdint.h>
/* Audio frame pacing (audio_pace.c). The game synthesizes one audio frame per
 * game tic; this sizes each frame from the DSP queue instead of assuming
 * exactly 60 tics per second. */
#define AUDIO_CHUNK_SAMPLES 184
/* The N64 buffers hold five chunks. Longer frames overrun the sound effect
 * player's per-frame event handling, so pacing stays within them. */
#define AUDIO_MAX_CHUNKS 5
typedef struct NativeAudioPace {int32_t lastQueued,lastMade;float played;int started;} NativeAudioPace;
int32_t nativeAudioPace(NativeAudioPace* pace,int32_t queued,int32_t rate);

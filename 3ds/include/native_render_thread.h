#pragma once
#include <stdint.h>
/* Display-list translation on the New 3DS's third core (render_thread.c). */
extern int native_render_async;
/* Bench timing: main-thread waits, tick start, submit offset, render work. */
extern uint64_t native_render_block_ticks,native_render_tick_start,native_render_submit_ticks,native_render_work_ticks;
void native_submit_display_list(void* dl);
/* Waits until the submitted frame no longer reads game memory; no-op on the
 * render thread. nativeRenderIdle also waits for its GPU submission. */
void nativeRenderWait(void);
void nativeRenderIdle(void);
void nativeRenderTranslated(void);
void nativeRenderStop(void);

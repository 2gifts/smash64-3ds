#pragma once
/* Four times the first release's maximum separation. Keep CPU culling and
 * the GPU eye transform in agreement; slider zero is still a single eye. */
#define NATIVE_STEREO_SHIFT_MAX 0.06f
/* Private no-op tags bracket only a match's wallpaper display list. The
 * marker survives deferred display-list submission and never classifies HUD
 * sprites, menus, or offscreen fighter previews as distant scenery. */
#define NATIVE_BACKDROP_BEGIN 0x53424b31u
#define NATIVE_BACKDROP_END   0x53424b30u
extern unsigned native_stereo_backdrop;

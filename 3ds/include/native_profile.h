#pragma once
/* Each installable profile keeps its own save, settings and reports.
 * The default (fresh save) profile keeps the original folder so existing
 * installs update in place; the unlocked profile is a separate title. */
#ifndef SSB_DATA_DIR
#define SSB_DATA_DIR "sdmc:/3ds/ssb64"
#endif
extern int native_profile_unlocked;

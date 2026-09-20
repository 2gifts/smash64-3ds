#include <lb/library.h>
/* The importer must match the actual ARM game ABI, including padding. */
_Static_assert(sizeof(LBBackupVSRecord)==92,"VS save record layout");
_Static_assert(sizeof(LBBackup1PRecord)==32,"1P save record layout");
_Static_assert(sizeof(LBBackupData)==1516,"save size");
_Static_assert(__builtin_offsetof(LBBackupData,signature)==1508,"signature offset");
_Static_assert(__builtin_offsetof(LBBackupData,checksum)==1512,"checksum offset");

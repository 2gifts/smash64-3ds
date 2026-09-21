#include <lb/library.h>
#include <sc/scene.h>
/* The importer must match the actual ARM game ABI, including padding. */
_Static_assert(sizeof(LBBackupVSRecord)==92,"VS save record layout");
_Static_assert(sizeof(LBBackup1PRecord)==32,"1P save record layout");
_Static_assert(sizeof(LBBackupData)==1516,"save size");
_Static_assert(__builtin_offsetof(LBBackupData,signature)==1508,"signature offset");
_Static_assert(__builtin_offsetof(LBBackupData,checksum)==1512,"checksum offset");
/* The credits' projection view aliases the live name record on both ARM32
 * and desktop ports. A shifted interpolation field leaves a highlight
 * attached after its target has been freed. */
_Static_assert(__builtin_offsetof(SCStaffrollMatrix,unk_gmcreditsmtx_0xC)==__builtin_offsetof(SCStaffrollName,offset_x),"credits width offset");
_Static_assert(__builtin_offsetof(SCStaffrollMatrix,unk_gmcreditsmtx_0x10)==__builtin_offsetof(SCStaffrollName,unkgmcreditsstruct0x10),"credits height offset");
_Static_assert(__builtin_offsetof(SCStaffrollMatrix,unk_gmcreditsmtx_0x14)==__builtin_offsetof(SCStaffrollName,interpolation),"credits lifetime offset");

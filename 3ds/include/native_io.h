#pragma once
#include <stddef.h>
typedef void (*NativeIoWrite)(const void*);
int nativeIoInit(void);
/* Copies immutable bytes. A nonzero key replaces an older pending job of
 * that kind; a running write always owns its private snapshot. */
int nativeIoSubmit(NativeIoWrite,const void*,size_t,unsigned key);
void nativeIoDrain(void);
void nativeIoExit(void);

#include "native_display.h"
#include "native_io.h"
#include "native_perf.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>
#ifndef DISPLAY_PATH
#define DISPLAY_PATH "sdmc:/3ds/ssb64/display.cfg"
#endif
volatile uint32_t native_widescreen;
void nativeDisplayLoad(void){
    native_widescreen=0;
    FILE* f=fopen(DISPLAY_PATH,"rb");if(!f)return;
    char buf[32]={0};size_t n=fread(buf,1,sizeof(buf),f);
    if((n==13&&!memcmp(buf,"widescreen=1\n",13))||
       (n==14&&!memcmp(buf,"widescreen=1\r\n",14)))native_widescreen=1;
    fclose(f);
}
static void writeDisplay(const void* data){
    unsigned value=*(const uint32_t*)data;
    /* Write only on deliberate taps. The game save and performance reports
     * have independent files. An interrupted/malformed setting defaults 4:3. */
    FILE* f=fopen(DISPLAY_PATH ".tmp","wb");if(!f)goto failed;
    int ok=fprintf(f,"widescreen=%u\n",value)==13;
    if(fflush(f))ok=0;if(fclose(f))ok=0;if(!ok)goto failed;
    if(remove(DISPLAY_PATH)&&errno!=ENOENT)goto failed;
    if(rename(DISPLAY_PATH ".tmp",DISPLAY_PATH))goto failed;
    return;
failed: __atomic_fetch_add(&native_perf_error,1,__ATOMIC_RELAXED);
}
int nativeDisplayToggle(void){
    native_widescreen=!native_widescreen;
    uint32_t value=native_widescreen;
    return nativeIoSubmit(writeDisplay,&value,sizeof(value),1);
}

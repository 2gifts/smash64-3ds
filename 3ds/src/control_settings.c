#include "native_controls.h"
#include "native_io.h"
#include "native_perf.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>
#ifndef CONTROLS_PATH
#define CONTROLS_PATH "sdmc:/3ds/ssb64/controls.cfg"
#endif
uint32_t native_tap_jump_disabled,native_cstick_enabled;
void nativeControlsLoad(void){
    native_tap_jump_disabled=native_cstick_enabled=0;
    FILE* f=fopen(CONTROLS_PATH,"rb");if(!f)return;
    char data[64]={0};size_t n=fread(data,1,sizeof(data)-1,f);fclose(f);
    unsigned tap,cstick;int end=0;
    if(sscanf(data,"tap_jump=%u\nc_stick=%u\n%n",&tap,&cstick,&end)==2&&end==n&&tap<=1&&cstick<=1){
        native_tap_jump_disabled=!tap;native_cstick_enabled=cstick;
    }
}
static void writeControls(const void* data){
    const uint32_t* values=data;
    FILE* f=fopen(CONTROLS_PATH ".tmp","wb");if(!f)goto failed;
    int ok=fprintf(f,"tap_jump=%u\nc_stick=%u\n",!values[0],values[1])>0;
    if(fflush(f))ok=0;if(fclose(f))ok=0;if(!ok)goto failed;
    if(remove(CONTROLS_PATH)&&errno!=ENOENT)goto failed;
    if(rename(CONTROLS_PATH ".tmp",CONTROLS_PATH))goto failed;
    return;
failed:__atomic_fetch_add(&native_perf_error,1,__ATOMIC_RELAXED);
}
int nativeControlsToggle(unsigned option){
    if(option==0)native_tap_jump_disabled=!native_tap_jump_disabled;
    else if(option==1)native_cstick_enabled=!native_cstick_enabled;
    else return -1;
    uint32_t values[]={native_tap_jump_disabled,native_cstick_enabled};
    return nativeIoSubmit(writeControls,values,sizeof(values),4);
}

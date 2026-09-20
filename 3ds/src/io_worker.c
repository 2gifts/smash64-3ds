#include <3ds.h>
#include <stdlib.h>
#include <string.h>
#include "native_io.h"
typedef struct Job {NativeIoWrite write;void* data;unsigned key;} Job;
static Job jobs[8];
static unsigned count,busy,stopping;
static LightLock lock;
static LightEvent wake;
static Thread worker;
static void run(void* unused){
    for(;;){
        LightLock_Lock(&lock);
        if(!count){unsigned done=stopping;LightLock_Unlock(&lock);if(done)return;LightEvent_Wait(&wake);continue;}
        Job job=jobs[0];memmove(jobs,jobs+1,(--count)*sizeof(Job));busy=1;
        LightLock_Unlock(&lock);
        job.write(job.data);free(job.data);
        LightLock_Lock(&lock);busy=0;LightLock_Unlock(&lock);
    }
}
int nativeIoInit(void){
    LightLock_Init(&lock);LightEvent_Init(&wake,RESET_ONESHOT);
    /* Lower priority than gameplay. FS service waits yield the application
     * core; CSV formatting uses time otherwise spent waiting for the GPU. */
    worker=threadCreate(run,NULL,32*1024,0x3f,-2,false);
    return worker?0:-1;
}
int nativeIoSubmit(NativeIoWrite write,const void* data,size_t bytes,unsigned key){
    if(!worker)return -1;
    void* copy=malloc(bytes);if(!copy)return -1;memcpy(copy,data,bytes);
    LightLock_Lock(&lock);
    if(key)for(unsigned i=0;i<count;i++)if(jobs[i].key==key){
        void* old=jobs[i].data;jobs[i]=(Job){write,copy,key};
        LightLock_Unlock(&lock);free(old);LightEvent_Signal(&wake);return 0;
    }
    if(count==8||stopping){LightLock_Unlock(&lock);free(copy);return -1;}
    jobs[count++]=(Job){write,copy,key};LightLock_Unlock(&lock);LightEvent_Signal(&wake);return 0;
}
void nativeIoDrain(void){
    if(!worker)return;
    for(;;){LightLock_Lock(&lock);unsigned pending=count||busy;LightLock_Unlock(&lock);if(!pending)return;svcSleepThread(1000000);}
}
void nativeIoExit(void){
    if(!worker)return;nativeIoDrain();LightLock_Lock(&lock);stopping=1;LightLock_Unlock(&lock);
    LightEvent_Signal(&wake);threadJoin(worker,U64_MAX);threadFree(worker);worker=NULL;
}

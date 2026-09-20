"""Run the actual bounded writer on Windows threads and immutable snapshots."""
import subprocess,json
from build import ROOT,OUT,BIN
def main():
    dst=OUT/'io-host-test';dst.mkdir(exist_ok=True)
    shim=r'''
#include <windows.h>
#include <stdint.h>
#include <stdbool.h>
typedef CRITICAL_SECTION LightLock;
typedef HANDLE LightEvent;
typedef struct HostThread {HANDLE h;void(*fn)(void*);void* arg;} *Thread;
#define RESET_ONESHOT 0
#define U64_MAX UINT64_MAX
static void LightLock_Init(LightLock* l){InitializeCriticalSection(l);}
static void LightLock_Lock(LightLock* l){EnterCriticalSection(l);}
static void LightLock_Unlock(LightLock* l){LeaveCriticalSection(l);}
static void LightEvent_Init(LightEvent* e,int unused){*e=CreateEvent(NULL,FALSE,FALSE,NULL);}
static void LightEvent_Wait(LightEvent* e){WaitForSingleObject(*e,INFINITE);}
static void LightEvent_Signal(LightEvent* e){SetEvent(*e);}
static DWORD WINAPI startThread(void* p){Thread t=p;t->fn(t->arg);return 0;}
static Thread threadCreate(void(*fn)(void*),void* arg,size_t stack,int priority,int core,bool detached){
    Thread t=calloc(1,sizeof(*t));t->fn=fn;t->arg=arg;t->h=CreateThread(NULL,stack,startThread,t,0,NULL);return t;}
static void threadJoin(Thread t,uint64_t timeout){WaitForSingleObject(t->h,INFINITE);}
static void threadFree(Thread t){CloseHandle(t->h);free(t);}
static void svcSleepThread(int64_t ns){Sleep((DWORD)(ns/1000000));}
'''
    source='#include <stdlib.h>\n'+shim+(ROOT/'src/io_worker.c').read_text().replace('#include <3ds.h>','')
    source+=r'''
#include <assert.h>
#include <stdio.h>
static HANDLE gate,entered;
static unsigned latest,ordered[16],n;
static void blocked(const void* p){SetEvent(entered);WaitForSingleObject(gate,INFINITE);assert(*(const unsigned*)p==123);}
static void setting(const void* p){latest=*(const unsigned*)p;}
static void report(const void* p){ordered[n++]=*(const unsigned*)p;}
int main(void){
    assert(nativeIoInit()==0);gate=CreateEvent(NULL,TRUE,FALSE,NULL);entered=CreateEvent(NULL,TRUE,FALSE,NULL);
    unsigned v=123;assert(nativeIoSubmit(blocked,&v,4,0)==0);v=999;WaitForSingleObject(entered,INFINITE);
    // A slow SD write never stalls submissions. Settings coalesce; reports keep order.
    for(v=0;v<10000;v++)assert(nativeIoSubmit(setting,&v,4,1)==0);
    for(v=0;v<7;v++)assert(nativeIoSubmit(report,&v,4,0)==0);
    assert(nativeIoSubmit(report,&v,4,0)==-1);assert(count==8);
    SetEvent(gate);nativeIoDrain();assert(latest==9999&&n==7);
    for(unsigned i=0;i<7;i++)assert(ordered[i]==i);
    nativeIoExit();assert(nativeIoSubmit(report,&v,4,0)==-1);
    puts("Immutable snapshots, 10000 coalesced settings, bounded queue, report ordering, drain and shutdown passed");
}
'''
    c=dst/'io.c';c.write_text(source);exe=dst/'io.exe'
    subprocess.run([str(BIN/'clang.exe'),'-O2','-I'+str(ROOT/'include'),str(c),'-o',str(exe)],check=True,capture_output=True,text=True)
    r=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
    result=dict(passed=True,detail=r.stdout.strip());(dst/'verified.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()

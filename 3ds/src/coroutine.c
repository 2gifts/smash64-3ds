#include "coroutine.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

typedef struct __attribute__((aligned(8))) {
    uint32_t r[8], sp, lr;
    double d[8];
} Context;
_Static_assert(sizeof(Context)==104,"ARM coroutine context size");
_Static_assert(offsetof(Context,d)==40,"ARM coroutine VFP register offset");
struct PortCoroutine {
    Context context, caller_context;
    PortCoroutine* caller;
    void (*entry)(void*);
    void* arg;
    void* stack;
    size_t stack_size;
    int finished;
};
static PortCoroutine* current;
extern void port_coroutine_swap(Context*,Context*);
extern void port_coroutine_trampoline_armv7(void);
extern void port_log(const char*,...);

void port_coroutine_init_main(void) {current=NULL;}
PortCoroutine* port_coroutine_create(void (*entry)(void*),void* arg,size_t size) {
    if(size<32768) size=32768;
    PortCoroutine* co=calloc(1,sizeof(*co));
    if(!co) return NULL;
    co->stack=malloc(size+32);
    if(!co->stack) {free(co);return NULL;}
    memset(co->stack,0xa5,32);
    co->stack_size=size;
    co->entry=entry; co->arg=arg;
    co->context.r[0]=(uintptr_t)co;
    co->context.sp=((uintptr_t)co->stack+size+32)&~(uintptr_t)7;
    co->context.lr=(uintptr_t)port_coroutine_trampoline_armv7;
    return co;
}
static void check_stack(PortCoroutine* co) {
    for(unsigned i=0;i<32;i++) if(((uint8_t*)co->stack)[i]!=0xa5) {
        port_log("Coroutine stack overflow entry=%p size=%u\n",co->entry,(unsigned)co->stack_size);
        abort();
    }
}
void port_coroutine_destroy(PortCoroutine* co) {
    if(!co)return;
    if(co==current)abort();
    check_stack(co); free(co->stack);free(co);
}
void port_coroutine_resume(PortCoroutine* co) {
    if(!co || co->finished)return;
    if(co==current)abort();
    co->caller=current; current=co;
    port_coroutine_swap(&co->caller_context,&co->context);
    current=co->caller;
    check_stack(co);
}
void port_coroutine_yield(void) {
    PortCoroutine* co=current;
    if(!co)abort();
    current=co->caller;
    port_coroutine_swap(&co->context,&co->caller_context);
    current=co;
}
void port_coroutine_trampoline_c(PortCoroutine* co) {
    co->entry(co->arg); co->finished=1;
    port_coroutine_yield();
    abort();
}
int port_coroutine_is_finished(PortCoroutine* co) {return !co || co->finished;}
int port_coroutine_in_coroutine(void) {return current!=NULL;}

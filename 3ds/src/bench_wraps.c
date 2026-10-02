/* Bench-only timing of asset reload stages (linked with --wrap in bench builds). */
#include <stdint.h>
#include <stddef.h>
extern unsigned long long nativeProfTick(void);
uint64_t native_load_ticks[4]; /* 0 total force-load, 1 byteswap, 2 halfswap registration, 3 fetch */
extern void* __real_lbRelocGetForceExternHeapFile(uint32_t,void*);
void* __wrap_lbRelocGetForceExternHeapFile(uint32_t id,void* heap){
    unsigned long long t=nativeProfTick();void* r=__real_lbRelocGetForceExternHeapFile(id,heap);native_load_ticks[0]+=nativeProfTick()-t;return r;}
extern void __real_portRelocByteSwapBlob(void*,size_t,unsigned);
void __wrap_portRelocByteSwapBlob(void* d,size_t n,unsigned id){
    unsigned long long t=nativeProfTick();__real_portRelocByteSwapBlob(d,n,id);native_load_ticks[1]+=nativeProfTick()-t;}
extern void __real_port_aobj_register_halfswapped_range(void*,unsigned long);
void __wrap_port_aobj_register_halfswapped_range(void* b,unsigned long n){
    unsigned long long t=nativeProfTick();__real_port_aobj_register_halfswapped_range(b,n);native_load_ticks[2]+=nativeProfTick()-t;}
uint64_t native_anim_ticks[2]; /* 0 stream unhalfswap, 1 interpolation visit */
extern void __real_port_aobj_event32_unhalfswap_stream(void*);
void __wrap_port_aobj_event32_unhalfswap_stream(void* h){
    unsigned long long t=nativeProfTick();__real_port_aobj_event32_unhalfswap_stream(h);native_anim_ticks[0]+=nativeProfTick()-t;}
extern int __real_port_aobj_unhalfswap_visit(const void*);
int __wrap_port_aobj_unhalfswap_visit(const void* p){
    unsigned long long t=nativeProfTick();int r=__real_port_aobj_unhalfswap_visit(p);native_anim_ticks[1]+=nativeProfTick()-t;return r;}

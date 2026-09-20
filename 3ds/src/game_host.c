#include <ssb_types.h>
#include <PR/os.h>
#include <sys/scheduler.h>
#include <sc/scene.h>
#include <mn/menu.h>
#include "coroutine.h"
#include "port_watchdog.h"
#include "native_perf.h"
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

extern uint64_t native_time_ticks(void);
extern void native_read_pad(uint16_t*,int8_t*,int8_t*);
extern void syMainLoop(void);
extern void port_vi_simulate_vblank(void);
extern void port_resume_service_threads(void);
extern void port_log(const char*,...);
extern void port_stats(const char*,...);
extern void native_submit_display_list(void*);
extern void port_fighter_seed_vanilla(void);

volatile uint32_t ssb_frame_count,ssb_display_lists;
volatile int ssb_active_thread;
volatile uintptr_t ssb_last_display_list;
static uint64_t timeOffset;

void port_watchdog_note_resume_start(int id) {ssb_active_thread=id;}
void port_watchdog_note_resume_end(int id) {ssb_active_thread=-1;}
void port_dump_backtrace(void) {port_log("frame=%u thread=%d\n",ssb_frame_count,ssb_active_thread);}
int port_get_frame_count(void) {return ssb_frame_count;}
int port_get_last_dl_defer_n(void) {return 1;}
void port_sim_load_stall(int n) {} /* Desktop timing estimator, not engine logic. */
void port_submit_display_list(void* dl) {
    ssb_display_lists++; ssb_last_display_list=(uintptr_t)dl;
    native_submit_display_list(dl);
}
static void boot(void* unused) {syMainLoop();}
void ssb_game_init(void) {
    port_fighter_seed_vanilla();
    port_coroutine_init_main();
    PortCoroutine* co=port_coroutine_create(boot,0,1024*1024);
    if(!co)abort();
    port_coroutine_resume(co);
    port_log("Native game boot yielded.\n");
    if(port_coroutine_is_finished(co))port_coroutine_destroy(co);
}
void ssb_game_tick(void) {
    static int lastScene=-1;
    port_vi_simulate_vblank();
    osSendMesg(&gSYSchedulerTaskMesgQueue,(OSMesg)1,OS_MESG_NOBLOCK);
    port_resume_service_threads();
    ssb_frame_count++;
    NativePerfGame* perf=&native_perf_game;
    perf->scene=gSCManagerSceneData.scene_curr;
    if(perf->scene==nSCKindMaps){extern s32 sMNMapsCursorSlot;perf->stage=sMNMapsCursorSlot;}
    perf->in_match=(perf->scene==nSCKindVSBattle||perf->scene==nSCKind1PGame||
        perf->scene==nSCKind1PBonusStage||perf->scene==nSCKind1PTrainingMode)&&gSCManagerBattleState!=NULL;
    if(perf->in_match){
        perf->stage=gSCManagerBattleState->gkind;perf->status=gSCManagerBattleState->game_status;
        perf->game_frame=gSCManagerBattleState->time_passed;
        for(unsigned i=0;i<4;i++){
            perf->fighter[i]=gSCManagerBattleState->players[i].fkind;
            perf->kind[i]=gSCManagerBattleState->players[i].pkind;
        }
    }
    if(lastScene!=gSCManagerSceneData.scene_curr){
        lastScene=gSCManagerSceneData.scene_curr;
        port_stats("SCENE frame=%u current=%u previous=%u\n",ssb_frame_count,lastScene,gSCManagerSceneData.scene_prev);
        if(lastScene==nSCKind1PGame || lastScene==nSCKind1PBonusStage || lastScene==nSCKind1PTrainingMode)
            port_stats("SINGLE_SETUP scene=%u stage=%u fighter=%u bonus_fighter=%u training_fighter=%u\n",
                lastScene,gSCManagerSceneData.spgame_stage,gSCManagerSceneData.fkind,
                gSCManagerSceneData.bonus_fkind,gSCManagerSceneData.training_man_fkind);
        if(lastScene==nSCKindVSBattle)port_stats("MATCH_SETUP stage=%u fighters=%u,%u,%u,%u kinds=%u,%u,%u,%u\n",
            gSCManagerTransferBattleState.gkind,gSCManagerTransferBattleState.players[0].fkind,
            gSCManagerTransferBattleState.players[1].fkind,gSCManagerTransferBattleState.players[2].fkind,
            gSCManagerTransferBattleState.players[3].fkind,gSCManagerTransferBattleState.players[0].pkind,
            gSCManagerTransferBattleState.players[1].pkind,gSCManagerTransferBattleState.players[2].pkind,gSCManagerTransferBattleState.players[3].pkind);
    }
    if(lastScene==nSCKindVSBattle&&ssb_frame_count%600==0)port_stats("MATCH_TICK frame=%u status=%u elapsed=%u remaining=%u falls=%d,%d\n",
        ssb_frame_count,gSCManagerBattleState->game_status,gSCManagerBattleState->time_passed,gSCManagerBattleState->time_remain,
        gSCManagerBattleState->players[0].falls,gSCManagerBattleState->players[1].falls);
    if((lastScene==nSCKindVSBattle||lastScene==nSCKind1PGame||lastScene==nSCKind1PBonusStage||lastScene==nSCKind1PTrainingMode)
        &&gSCManagerBattleState&&ssb_frame_count%60==0)
        port_stats("PLAY_TICK frame=%u scene=%u status=%u elapsed=%u remaining=%u\n",ssb_frame_count,lastScene,
            gSCManagerBattleState->game_status,gSCManagerBattleState->time_passed,gSCManagerBattleState->time_remain);
    if(lastScene==nSCKindPlayersVS && (ssb_frame_count==430||ssb_frame_count==470)){
        extern MNPlayersSlotVS sMNPlayersVSSlots[];
        MNPlayersSlotVS* slot=&sMNPlayersVSSlots[0];
        if(slot->cursor)port_log("CSS frame=%u cursor=%.2f,%.2f fighter=%d selected=%d held=%d\n",ssb_frame_count,
            SObjGetStruct(slot->cursor)->pos.x,SObjGetStruct(slot->cursor)->pos.y,slot->fkind,slot->is_selected,slot->held_player);
    }
}
OSTime ssb_osGetTime(void) {return native_time_ticks()+timeOffset;}
void osSetTime(OSTime time) {timeOffset=time-native_time_ticks();}
u32 osGetCount(void) {return (u32)native_time_ticks();}
u64 osVirtualToPhysical(void* p) {return (uintptr_t)p;}
void osInvalDCache(void* p,s32 size) {} /* CPU-owned, coherent native memory. */
void osWritebackDCache(void* p,s32 size) {}
void osWritebackDCacheAll(void) {}
static OSPiHandle cartridge;
OSPiHandle* osCartRomInit(void) {return &cartridge;}
void osCreatePiManager(OSPri p,OSMesgQueue*q,OSMesg*m,s32 n) {osCreateMesgQueue(q,m,n);}
s32 osEPiStartDma(OSPiHandle*h,OSIoMesg*m,s32 dir) {
    port_log("Unexpected native ROM DMA addr=%lx size=%u\n",(unsigned long)m->devAddr,m->size);
    abort();
}
s32 osContInit(OSMesgQueue*q,u8* bits,OSContStatus* status) {
    *bits=1;
    memset(status,0,sizeof(OSContStatus)*4);
    status[0].type=CONT_ABSOLUTE;
    for(int i=1;i<4;i++)status[i].errno=CONT_NO_RESPONSE_ERROR;
    return 0;
}
s32 osContStartReadData(OSMesgQueue*q) {return osSendMesg(q,0,OS_MESG_NOBLOCK);}
void osContGetReadData(OSContPad* pad) {
    memset(pad,0,sizeof(OSContPad)*4);
    native_read_pad(&pad[0].button,&pad[0].stick_x,&pad[0].stick_y);
    for(int i=1;i<4;i++)pad[i].errno=CONT_NO_RESPONSE_ERROR;
}
s32 osMotorInit(OSMesgQueue*q,OSPfs*p,int channel) {return PFS_ERR_NOPACK;}
s32 __osMotorAccess(OSPfs*p,s32 flag) {return PFS_ERR_NOPACK;}

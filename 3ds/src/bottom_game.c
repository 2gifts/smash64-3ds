#include <sc/scene.h>
#include <mn/menu.h>
#include "native_bottom.h"
#include <string.h>
extern MNPlayersSlotVS sMNPlayersVSSlots[4];
extern MNPlayersSlot1PGame sMNPlayers1PGameSlot;
extern MNPlayersSlotTraining sMNPlayers1PTrainingSlots[4];
extern MNPlayersSlotBonus sMNPlayers1PBonusSlot;
extern s32 sMNPlayersVSGameRule,sMNPlayersVSIsTeamBattle,sMNPlayersVSStockValue,sMNPlayersVSTimeValue;
extern s32 sMNPlayers1PTrainingManPlayer,sMNPlayers1PTrainingComPlayer;
extern s32 sMNPlayers1PBonusManPlayer,sMNPlayers1PGameStockValue,sMNPlayers1PGameTimeSetting;
extern s32 mnVSResultsGetDisplayPlace(s32 player);
extern s32 sMNVSResultsKind;
static NativeBottomState lastBattle;
static unsigned hadBattle,frozen,lastScene=~0u;
extern volatile uint32_t ssb_frame_count;
static struct {unsigned attacker,hits;} chains[4];
static unsigned comboHits[4],comboUntil[4],comboLastFrame;
extern void __real_ftParamUpdatePlayerBattleStats(s32,s32,s32);
void __wrap_ftParamUpdatePlayerBattleStats(s32 attacker,s32 defender,s32 damage){
    if((unsigned)defender<4&&(unsigned)attacker<4&&attacker!=defender&&gSCManagerBattleState){
        /* This is the same hit event used by Training Mode. The original
         * ftMain update clears combo_count_foe when hitstun ends. No timer
         * determines whether hits belong to a combo. */
        if(!gSCManagerBattleState->players[defender].combo_count_foe||chains[defender].attacker!=(unsigned)attacker)
            chains[defender].hits=0;
        chains[defender].attacker=attacker;chains[defender].hits++;
        comboHits[attacker]=chains[defender].hits;comboUntil[attacker]=75;
    }
    __real_ftParamUpdatePlayerBattleStats(attacker,defender,damage);
}
static void combos(NativeBottomState* s,const SCBattleState* b){
    unsigned active[4]={0};
    for(unsigned d=0;d<4;d++){
        if(!b->players[d].combo_count_foe)chains[d].hits=0;
        if(chains[d].hits>=2&&chains[d].attacker<4)active[chains[d].attacker]=1;
    }
    for(unsigned a=0;a<4;a++){
        if(b->game_status==1&&ssb_frame_count!=comboLastFrame&&!active[a]&&comboUntil[a])comboUntil[a]--;
        s->players[a].combo_hits=comboUntil[a]?comboHits[a]:0;
        s->players[a].combo_active=active[a];
    }
    comboLastFrame=ssb_frame_count;
}
static unsigned clamp(int n,unsigned hi){return n<0?0:(unsigned)n>hi?hi:(unsigned)n;}
static void rules(NativeBottomState* s,const SCBattleState* b){
    s->stage=b->gkind;s->stock_mode=(b->game_rules&SCBATTLE_GAMERULE_STOCK)!=0;s->teams=b->is_team_battle;
    s->rule_stocks=b->stocks+1;s->rule_minutes=b->time_limit;
    s->timer=(b->game_rules&SCBATTLE_GAMERULE_TIME)&&b->time_limit!=SCBATTLE_TIMELIMIT_INFINITE;
}
static void player(NativeBottomPlayer* p,const SCPlayerData* q,unsigned slot,unsigned teams){
    p->kind=q->pkind;p->character=q->fkind;p->costume=q->costume;
    p->color=teams?(q->team==2?3:q->team):slot;
    p->damage=clamp(q->stock_damage_all,999);p->stocks=clamp(q->stock_count+1,100);
    if(q->fkind==nFTKindBoss)p->damage=clamp(300-q->stock_damage_all,300);
    p->level=q->level;p->ready=1;p->falls=q->falls;p->score=q->score;
    p->kos=q->score;
}
void nativeBottomSnapshot(NativeBottomState* s){
    unsigned sc=gSCManagerSceneData.scene_curr;
    memset(s,0,sizeof(*s));s->scene=sc;s->stage=~0u;
    for(unsigned i=0;i<4;i++){s->players[i].kind=2;s->players[i].character=~0u;}
    if(sc!=lastScene){frozen=0;lastScene=sc;memset(chains,0,sizeof(chains));memset(comboHits,0,sizeof(comboHits));memset(comboUntil,0,sizeof(comboUntil));}
    if(sc==nSCKindVSBattle||sc==nSCKind1PGame||sc==nSCKind1PBonusStage||sc==nSCKind1PTrainingMode){
        const SCBattleState* b=gSCManagerBattleState;if(!b)return;
        if(frozen&&b->game_status>=5){*s=lastBattle;return;}
        frozen=0;
        s->page=BOTTOM_BATTLE;rules(s,b);s->status=b->game_status;
        s->sudden_death=sc==nSCKindVSBattle&&gSCManagerSceneData.is_suddendeath;
        s->training=sc==nSCKind1PTrainingMode;s->bonus=sc==nSCKind1PBonusStage;
        s->seconds=s->timer?(b->time_remain+59)/60:b->time_passed/60;
        for(unsigned i=0;i<4;i++){
            player(&s->players[i],&b->players[i],i,s->teams);
            s->players[i].stock_limited=!s->training&&!s->bonus&&
                (s->stock_mode||(sc==nSCKind1PGame&&b->players[i].pkind==0));
        }
        if(b->game_status==0){memset(chains,0,sizeof(chains));memset(comboUntil,0,sizeof(comboUntil));}
        combos(s,b);
        lastBattle=*s;hadBattle=1;if(b->game_status>=5)frozen=1;
    }else if(sc==nSCKindVSResults&&hadBattle){
        *s=lastBattle;s->scene=sc;s->page=BOTTOM_RESULTS;
        /* Sudden Death has its own battle state and restricted roster. The
         * official results use the original match's transfer state. */
        rules(s,&gSCManagerTransferBattleState);s->sudden_death=0;
        for(unsigned i=0;i<4;i++){
            memset(&s->players[i],0,sizeof(s->players[i]));
            player(&s->players[i],&gSCManagerTransferBattleState.players[i],i,s->teams);
            s->players[i].place=sMNVSResultsKind==nMNVSResultsKindNoContest?0:clamp(mnVSResultsGetDisplayPlace(i),4);
        }
    }else if(sc==nSCKindPlayersVS){
        s->page=BOTTOM_SELECT;rules(s,&gSCManagerTransferBattleState);
        s->stock_mode=(sMNPlayersVSGameRule&SCBATTLE_GAMERULE_STOCK)!=0;
        s->teams=sMNPlayersVSIsTeamBattle;s->rule_stocks=clamp(sMNPlayersVSStockValue+1,100);s->rule_minutes=clamp(sMNPlayersVSTimeValue,100);
        for(unsigned i=0;i<4;i++){
            MNPlayersSlotVS* q=&sMNPlayersVSSlots[i];NativeBottomPlayer* p=&s->players[i];
            p->kind=q->pkind;p->character=q->fkind;p->costume=q->costume;p->level=q->cpu_level;
            p->color=s->teams?(q->team==2?3:q->team):i;p->ready=q->is_fighter_selected;
        }
    }else if(sc==nSCKind1PGamePlayers||sc==nSCKind1PBonus1Players||sc==nSCKind1PBonus2Players){
        s->page=BOTTOM_SELECT;s->stock_mode=sc==nSCKind1PGamePlayers;
        unsigned i=s->stock_mode?gSCManagerSceneData.player:clamp(sMNPlayers1PBonusManPlayer,3);
        if(i>3)i=0;NativeBottomPlayer* p=&s->players[i];p->kind=0;p->color=i;
        if(s->stock_mode){p->character=sMNPlayers1PGameSlot.fkind;p->costume=sMNPlayers1PGameSlot.costume;p->ready=sMNPlayers1PGameSlot.is_fighter_selected;
            s->rule_stocks=clamp(sMNPlayers1PGameStockValue+1,100);s->rule_minutes=clamp(sMNPlayers1PGameTimeSetting,100);
        }else{p->character=sMNPlayers1PBonusSlot.fkind;p->costume=sMNPlayers1PBonusSlot.costume;p->ready=sMNPlayers1PBonusSlot.is_fighter_selected;s->bonus=1;}
    }else if(sc==nSCKindPlayers1PTraining){
        s->page=BOTTOM_SELECT;s->training=1;
        for(unsigned i=0;i<4;i++)if(i==sMNPlayers1PTrainingManPlayer||i==sMNPlayers1PTrainingComPlayer){
            MNPlayersSlotTraining* q=&sMNPlayers1PTrainingSlots[i];NativeBottomPlayer* p=&s->players[i];
            p->kind=i==sMNPlayers1PTrainingManPlayer?0:1;p->color=i;p->character=q->fkind;
            p->costume=q->costume;p->ready=q->is_fighter_selected;p->level=q->cpu_level;
        }
    }else if(sc==nSCKindMaps){
        s->page=BOTTOM_STAGE;rules(s,&gSCManagerTransferBattleState);
        for(unsigned i=0;i<4;i++)player(&s->players[i],&gSCManagerTransferBattleState.players[i],i,s->teams);
    }else if(sc==nSCKindVSMode||sc==nSCKindVSOptions||sc==nSCKindVSItemSwitch)rules(s,&gSCManagerTransferBattleState);
}

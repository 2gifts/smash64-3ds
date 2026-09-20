"""Exercise the real game-to-HUD bridge against original engine structs."""
import json,subprocess,re
from build import ROOT,OUT,BIN,DECOMP,game_flags

def main():
    dst=OUT/'bottom-state-test';dst.mkdir(exist_ok=True)
    source='''
#include <assert.h>
#include <stdio.h>
#include "../src/bottom_game.c"
volatile uint32_t ssb_frame_count;
void __real_ftParamUpdatePlayerBattleStats(s32 a,s32 d,s32 damage){
 if((unsigned)a<4&&(unsigned)d<4&&a!=d)gSCManagerBattleState->players[d].combo_count_foe++;
}
SCCommonData gSCManagerSceneData;
SCBattleState battle,gSCManagerTransferBattleState;
SCBattleState* gSCManagerBattleState=&battle;
MNPlayersSlotVS sMNPlayersVSSlots[4];
MNPlayersSlot1PGame sMNPlayers1PGameSlot;
MNPlayersSlotTraining sMNPlayers1PTrainingSlots[4];
MNPlayersSlotBonus sMNPlayers1PBonusSlot;
s32 sMNPlayersVSGameRule,sMNPlayersVSIsTeamBattle,sMNPlayersVSStockValue,sMNPlayersVSTimeValue;
s32 sMNPlayers1PTrainingManPlayer,sMNPlayers1PTrainingComPlayer;
s32 sMNPlayers1PBonusManPlayer,sMNPlayers1PGameStockValue,sMNPlayers1PGameTimeSetting;
s32 sMNVSResultsPlaces[4];
s32 sMNVSResultsKind,sMNVSResultsIsTeamBattle;
sb32 sMNVSResultsIsPresent[4];
// ORIGINAL_RESULTS_FUNCTIONS
#undef assert
#define assert(x) do { if(!(x)){fprintf(stderr,"failed at line %d\\n",__LINE__);return 1;} }while(0)
int main(void){
    NativeBottomState s;
    gSCManagerSceneData.scene_curr=nSCKindVSBattle;
    battle.game_rules=SCBATTLE_GAMERULE_STOCK;battle.game_status=1;battle.stocks=3;
    battle.players[0].pkind=0;battle.players[0].fkind=8;battle.players[0].stock_count=3;battle.players[0].stock_damage_all=124;
    nativeBottomSnapshot(&s);assert(s.page==BOTTOM_BATTLE&&s.players[0].damage==124&&s.players[0].stocks==4&&s.players[0].stock_limited);
    __wrap_ftParamUpdatePlayerBattleStats(0,1,5);__wrap_ftParamUpdatePlayerBattleStats(0,1,5);
    nativeBottomSnapshot(&s);assert(s.players[0].combo_hits==2&&s.players[0].combo_active);
    __wrap_ftParamUpdatePlayerBattleStats(2,1,5);nativeBottomSnapshot(&s);assert(s.players[2].combo_hits==1);
    __wrap_ftParamUpdatePlayerBattleStats(2,1,5);nativeBottomSnapshot(&s);assert(s.players[2].combo_hits==2);
    battle.players[1].combo_count_foe=0;nativeBottomSnapshot(&s);assert(!s.players[2].combo_active);
    __wrap_ftParamUpdatePlayerBattleStats(2,1,5);nativeBottomSnapshot(&s);assert(s.players[2].combo_hits==1);
    __wrap_ftParamUpdatePlayerBattleStats(4,1,5);__wrap_ftParamUpdatePlayerBattleStats(1,1,5);
    nativeBottomSnapshot(&s);assert(s.players[2].combo_hits==1);
    battle.players[1].combo_count_foe=0;
    for(unsigned f=0;f<76;f++){ssb_frame_count++;nativeBottomSnapshot(&s);}
    assert(!s.players[2].combo_hits);
    battle.players[0].stock_count=0;nativeBottomSnapshot(&s);assert(s.players[0].stocks==1);
    battle.players[0].stock_count=-1;nativeBottomSnapshot(&s);assert(s.players[0].stocks==0);
    battle.players[1].pkind=1;battle.players[1].fkind=nFTKindBoss;battle.players[1].stock_damage_all=245;
    nativeBottomSnapshot(&s);assert(s.players[1].damage==55);
    battle.players[1].stock_damage_all=301;nativeBottomSnapshot(&s);assert(!s.players[1].damage);
    battle.game_rules=SCBATTLE_GAMERULE_TIME;battle.time_limit=1;battle.time_remain=3599;
    battle.players[0].total_kos_players[1]=3;battle.players[0].total_kos_players[2]=2;battle.players[0].falls=4;
    battle.players[0].score=5;
    nativeBottomSnapshot(&s);assert(s.timer&&s.seconds==60&&!s.players[0].stock_limited&&s.players[0].kos==5&&s.players[0].falls==4);
    battle.game_status=5;nativeBottomSnapshot(&s);gSCManagerTransferBattleState=battle;battle.players[0].stock_damage_all=0;
    nativeBottomSnapshot(&s);assert(s.players[0].damage==124);
    battle.game_status=0;gSCManagerSceneData.is_suddendeath=1;battle.players[0].stock_damage_all=300;
    nativeBottomSnapshot(&s);assert(s.sudden_death&&s.status==0&&s.players[0].damage==300);
    battle.game_status=1;nativeBottomSnapshot(&s);assert(s.sudden_death&&s.status==1);
    battle.game_status=5;nativeBottomSnapshot(&s);battle.players[0].stock_damage_all=0;
    gSCManagerSceneData.scene_curr=nSCKindVSResults;sMNVSResultsPlaces[0]=2;
    nativeBottomSnapshot(&s);assert(s.page==BOTTOM_RESULTS&&!s.sudden_death&&s.players[0].place==3&&s.players[0].kos==5);
    for(unsigned i=0;i<4;i++)sMNVSResultsIsPresent[i]=TRUE;
    sMNVSResultsPlaces[1]=0;sMNVSResultsPlaces[2]=sMNVSResultsPlaces[3]=1;
    nativeBottomSnapshot(&s);assert(s.players[0].place==4&&s.players[1].place==1&&s.players[2].place==2&&s.players[3].place==2);
    sMNVSResultsKind=nMNVSResultsKindNoContest;nativeBottomSnapshot(&s);assert(!s.players[0].place);
    gSCManagerSceneData.scene_curr=nSCKindPlayersVS;sMNPlayersVSGameRule=SCBATTLE_GAMERULE_STOCK;sMNPlayersVSStockValue=3;
    sMNPlayersVSSlots[0].pkind=0;sMNPlayersVSSlots[0].fkind=10;sMNPlayersVSSlots[0].is_fighter_selected=1;
    sMNPlayersVSSlots[1].pkind=2;sMNPlayersVSIsTeamBattle=1;sMNPlayersVSSlots[0].team=2;
    nativeBottomSnapshot(&s);assert(s.page==BOTTOM_SELECT&&s.rule_stocks==4&&s.players[0].character==10&&s.players[0].ready&&s.players[0].color==3&&s.players[1].kind==2);
    gSCManagerSceneData.scene_curr=nSCKind1PTrainingMode;battle.game_status=1;
    nativeBottomSnapshot(&s);assert(s.training&&!s.players[0].stock_limited&&s.players[0].damage==0);
    gSCManagerSceneData.scene_curr=nSCKindTitle;
    nativeBottomSnapshot(&s);assert(s.page==BOTTOM_MENU&&s.players[0].kind==2);
    puts("engine structs: live damage, remaining stocks, elimination, boss HP, timer, KO/falls, frozen results, team colors, CSS, training and scene reset passed");
}
'''.replace('#include "../src/bottom_game.c"','#include "'+(ROOT/'src/bottom_game.c').as_posix()+'"')
    c=dst/'state.c';c.write_text(source);exe=dst/'state.exe'
    original=(DECOMP/'src/mn/mnvsmode/mnvsresults.c').read_text()
    functions=[re.search(r's32 '+name+r'\([^\n]*\)\n\{.*?\n\}',original,re.S)[0] for name in ['mnVSResultsGetPresentCount','mnVSResultsGetPlayerCountPlace','mnVSResultsGetDisplayPlace']]
    c.write_text(source.replace('// ORIGINAL_RESULTS_FUNCTIONS','\n'.join(functions)))
    flags=[f for f in game_flags() if f.startswith('-D') or f.startswith('-I')]
    flags=[f for f in flags if f not in ['-D__3DS__','-D__assert=ssb_assert'] and 'libctru' not in f]
    p=subprocess.run([str(BIN/'clang.exe'),'-O2','-Wno-int-conversion','-Wno-pointer-to-int-cast',*flags,str(c),'-o',str(exe)],capture_output=True,text=True)
    (dst/'compile.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr[-5000:]
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
    evidence=dict(passed=True,detail=result.stdout.strip());(dst/'verified.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()

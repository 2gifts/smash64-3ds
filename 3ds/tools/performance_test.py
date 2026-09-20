"""Run the real aggregation/writer code against controlled frame timing."""
import csv,json,subprocess
from pathlib import Path
from build import ROOT,OUT,BIN

def main():
    dst=OUT/'perf-host-test';dst.mkdir(exist_ok=True)
    data=dst/'data';data.mkdir(exist_ok=True)
    for p in data.glob('*.csv'):p.unlink()
    source=(ROOT/'src/performance.c').read_text().replace('#include <3ds.h>', '#include <stdint.h>\n#define SYSCLOCK_ARM11 268123480\nstatic unsigned linearSpaceFree(void){return 24*1024*1024;}')
    source=source.replace('#include <sys/stat.h>','').replace('mkdir(PERF_PATH,0777);','(void)0;')
    source=source.replace('#define PERF_PATH "sdmc:/3ds/ssb64/perf"','#define PERF_PATH "'+data.relative_to(ROOT).as_posix()+'"')
    source+='''
int nativeIoSubmit(NativeIoWrite fn,const void* data,size_t n,unsigned key){fn(data);return 0;}
'''
    source+='''
#include <assert.h>
volatile uint32_t native_widescreen;
int main(void){
    nativePerfInit();uint64_t tick=1;unsigned lists=0;
    native_perf_game=(NativePerfGame){.scene=22,.stage=2,.status=1,.in_match=1};
    native_perf_render=(NativePerfRender){.batches=700,.vertices=18000,.texture_hits=900,.texture_misses=2,.upload_bytes=2048,.eyes=2,.submit_ms=8,.gpu_previous_ms=5,.slider=1,.wait_ms=3,.replay_ms=2,.audio_ms=1,.render_total_ms=3,.draw_calls=400,.texture_binds=100,.fog_uploads=2,.command_bytes=10240};
    native_perf_render.bottom_ms=0.75f;
    for(unsigned i=0;i<31001;i++){
        tick+=SYSCLOCK_ARM11/60;native_perf_game.game_frame++;
        nativePerfTick(tick,SYSCLOCK_ARM11/200,++lists,0);
    }
    assert(native_perf_saved==0 && row_seconds==2 && total.frames+current.frames==31000);
    uint64_t previous=total.ticks+current.ticks;
    native_perf_game.status=2;
    for(unsigned i=0;i<600;i++){tick+=SYSCLOCK_ARM11/60;nativePerfTick(tick,0,++lists,0);}
    native_perf_game.status=1;tick+=SYSCLOCK_ARM11/60;nativePerfTick(tick,0,++lists,0);
    assert(total.ticks+current.ticks==previous);
    tick+=SYSCLOCK_ARM11/20;nativePerfTick(tick,SYSCLOCK_ARM11/200,++lists,1);
    native_perf_game.status=5;nativePerfTick(tick,0,lists,1);
    assert(native_perf_saved==1 && total.frames==31001 && row_count<=480 && total.audio_drops==1);
    unsigned sum=0,hist=0;
    for(unsigned i=0;i<row_count;i++)sum+=rows[i].frames;
    for(unsigned i=0;i<HIST_BINS;i++)hist+=histogram[i];
    assert(sum==31001 && hist==31001);
    for(unsigned m=0;m<9;m++){
        native_perf_game.status=1;native_perf_game.game_frame=0;
        for(unsigned i=0;i<121;i++){
            tick+=SYSCLOCK_ARM11/60;native_perf_game.game_frame++;
            nativePerfTick(tick,SYSCLOCK_ARM11/200,++lists,1);
        }
        nativePerfFinish("test_rotation");
    }
    assert(native_perf_saved==10 && native_perf_error==0);
    sequence=1;nativePerfInit();assert(sequence==11);
    native_perf_game.in_match=0;native_perf_game.scene=21;native_widescreen=1;
    for(unsigned i=0;i<121;i++){
        tick+=SYSCLOCK_ARM11/60;nativePerfTick(tick,SYSCLOCK_ARM11/200,++lists,1);
    }
    assert(menu_dirty && menus[21].frames==120);
    nativePerfResetClock();tick+=SYSCLOCK_ARM11*10ull;nativePerfTick(tick,0,++lists,1);
    assert(menus[21].frames==120);
    nativePerfFinish("app_exit");assert(!menu_dirty);
    printf("frames, pause exclusion, compaction, finish and rotation passed; row RAM=%zu bytes\\n",sizeof(rows));
    return 0;
}
'''
    (dst/'performance-host.c').write_text(source)
    exe=dst/'performance-host.exe'
    subprocess.run([str(BIN/'clang.exe'),'-O2','-I'+str(ROOT/'include'),str(dst/'performance-host.c'),'-o',str(exe)],check=True,capture_output=True,text=True)
    result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
    files=list(data.glob('match-*.csv'));assert len(files)==8
    sequences=[]
    for p in files:
        lines=p.read_text().splitlines();sequences.append(int(lines[0].split('sequence=')[1].split()[0]))
        rows=list(csv.DictReader(l for l in lines if not l.startswith('#')))
        assert sum(int(r['frames']) for r in rows)==120
        assert all(59.9<float(r['fps'])<60.1 for r in rows)
        assert all(float(r['stereo_percent'])==100 and float(r['widescreen_percent'])==0 for r in rows)
        assert all(float(r['bottom_screen_ms'])==0.75 for r in rows)
        assert all(float(r['render_wait_ms'])==3 and float(r['audio_synth_ms'])==1 and
                   float(r['draw_calls_per_frame'])==400 and float(r['command_kib_per_frame'])==10 for r in rows)
    assert sorted(sequences)==list(range(3,11))
    menu_rows=list(csv.DictReader(l for l in (data/'menus.csv').read_text().splitlines() if not l.startswith('#')))
    assert len(menu_rows)==1 and menu_rows[0]['scene']=='21' and menu_rows[0]['frames']=='120'
    assert float(menu_rows[0]['widescreen_percent'])==100
    assert float(menu_rows[0]['bottom_screen_ms'])==0.75
    events=list(csv.DictReader(l for l in (data/'events.csv').read_text().splitlines() if not l.startswith('#')))
    assert len(events)<=64 and any(e['event']=='62' for e in events)
    evidence={'bounded_transition_events_verified':True,'bottom_screen_tracking_verified':True,'widescreen_tracking_verified':True,'passed':True,'detail':result.stdout.strip(),'retained_sequences':sorted(sequences),'files':len(files),'bytes':sum(p.stat().st_size for p in files),'menu_summary_frames':120,'additional_metrics_verified':True}
    (dst/'verified.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()

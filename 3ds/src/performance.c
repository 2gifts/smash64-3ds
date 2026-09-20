#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include "native_perf.h"
#include "native_display.h"
#include "native_io.h"

#define PERF_ROWS 480
#define PERF_FILES 8
#define HIST_BINS 1025
#define PERF_PATH "sdmc:/3ds/ssb64/perf"
NativePerfGame native_perf_game;
NativePerfRender native_perf_render;
uint32_t native_perf_saved,native_perf_error;
uint32_t native_asset_reads,native_asset_hits,native_asset_bytes;
static struct PerfRow {
    uint64_t ticks,work_ticks,batches,vertices,upload_bytes;
    float submit_ms,gpu_ms,slider_min,slider_max;
    uint32_t frames,last_frame,worst_us,over18,over25,over33,over50;
    uint32_t texture_hits,texture_misses,audio_drops,stereo_frames,linear_min;
    float wait_ms,replay_ms,audio_ms,game_ms;
    uint64_t draw_calls,texture_binds,fog_uploads,command_bytes;
    uint32_t wide_frames;
    float bottom_ms;
    uint64_t asset_reads,asset_hits,asset_bytes;
} rows[PERF_ROWS],current,total;
static struct PerfRow menus[62];
typedef struct EventRow {uint64_t ticks,work,reads,hits,bytes;uint32_t count,worst_us;} EventRow;
static EventRow events[64];
static uint64_t event_tick;
static uint32_t event_scene=~0u,event_stage=~0u,event_status;
typedef struct MenuSnapshot {struct PerfRow menus[62];EventRow events[64];} MenuSnapshot;
static uint64_t menu_last_tick;
static uint32_t menu_last_scene,menu_last_lists,menu_last_drops,menu_dirty;
static NativePerfGame match;
static uint32_t histogram[HIST_BINS],row_count,row_seconds=1,sequence=1;
static uint32_t last_lists,last_drops,active;
static uint64_t last_tick;
static time_t started;

typedef struct PerfSnapshot {
    struct PerfRow rows[PERF_ROWS],total;
    NativePerfGame match;
    uint32_t histogram[HIST_BINS],row_count,row_seconds,sequence;
    time_t started;
    char reason[32];
} PerfSnapshot;
static void writeError(void){__atomic_fetch_add(&native_perf_error,1,__ATOMIC_RELAXED);}
static void merge(struct PerfRow* a,const struct PerfRow* b) {
    if(!a->frames){*a=*b;return;}
    a->ticks+=b->ticks;a->work_ticks+=b->work_ticks;a->batches+=b->batches;
    a->vertices+=b->vertices;a->upload_bytes+=b->upload_bytes;
    a->submit_ms+=b->submit_ms;a->gpu_ms+=b->gpu_ms;
    a->frames+=b->frames;a->last_frame=b->last_frame;
    if(b->worst_us>a->worst_us)a->worst_us=b->worst_us;
    if(b->slider_min<a->slider_min)a->slider_min=b->slider_min;
    if(b->slider_max>a->slider_max)a->slider_max=b->slider_max;
    if(b->linear_min<a->linear_min)a->linear_min=b->linear_min;
    a->over18+=b->over18;a->over25+=b->over25;a->over33+=b->over33;a->over50+=b->over50;
    a->texture_hits+=b->texture_hits;a->texture_misses+=b->texture_misses;
    a->audio_drops+=b->audio_drops;a->stereo_frames+=b->stereo_frames;
    a->wait_ms+=b->wait_ms;a->replay_ms+=b->replay_ms;a->audio_ms+=b->audio_ms;a->game_ms+=b->game_ms;
    a->draw_calls+=b->draw_calls;a->texture_binds+=b->texture_binds;
    a->fog_uploads+=b->fog_uploads;a->command_bytes+=b->command_bytes;
    a->wide_frames+=b->wide_frames;a->bottom_ms+=b->bottom_ms;
    a->asset_reads+=b->asset_reads;a->asset_hits+=b->asset_hits;a->asset_bytes+=b->asset_bytes;
}
static void storeRow(void) {
    if(!current.frames)return;
    current.linear_min=linearSpaceFree();
    merge(&total,&current);
    if(row_count==PERF_ROWS){
        /* Retain the whole match: coarsen old and future windows together. */
        for(unsigned i=0;i<PERF_ROWS/2;i++){
            rows[i]=rows[i*2];merge(&rows[i],&rows[i*2+1]);
        }
        row_count=PERF_ROWS/2;row_seconds*=2;
    }
    rows[row_count++]=current;memset(&current,0,sizeof(current));
}
static double percentile(const PerfSnapshot* p,unsigned percent) {
    uint32_t target=((uint64_t)p->total.frames*percent+99)/100,n=0;
    for(unsigned i=0;i<HIST_BINS;i++){
        n+=p->histogram[i];
        if(n>=target)return i==HIST_BINS-1?p->total.worst_us/1000.0:(i+1)*0.25;
    }
    return p->total.worst_us/1000.0;
}
static void writeRow(FILE* f,const struct PerfRow* r) {
    double seconds=(double)r->ticks/SYSCLOCK_ARM11;
    fprintf(f,"%lu,%lu,%.4f,%.2f,%.3f,%lu,%lu,%lu,%lu,%.3f,%.3f,%.3f,%.1f,%.1f,%lu,%lu,%.2f,%lu,%.1f,%.3f,%.3f,%lu,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f,%.2f,%.1f,%.3f,%llu,%llu,%.2f\n",
        (unsigned long)r->last_frame,(unsigned long)r->frames,seconds,r->frames/seconds,r->worst_us/1000.0,
        (unsigned long)r->over18,(unsigned long)r->over25,(unsigned long)r->over33,(unsigned long)r->over50,
        (double)r->work_ticks*1000/SYSCLOCK_ARM11/r->frames,r->submit_ms/r->frames,r->gpu_ms/r->frames,
        (double)r->batches/r->frames,(double)r->vertices/r->frames,
        (unsigned long)r->texture_hits,(unsigned long)r->texture_misses,r->upload_bytes/1024.0,
        (unsigned long)r->audio_drops,100.0*r->stereo_frames/r->frames,r->slider_min,r->slider_max,
        (unsigned long)(r->linear_min/1024),
        r->wait_ms/r->frames,r->replay_ms/r->frames,r->audio_ms/r->frames,r->game_ms/r->frames,
        (double)r->draw_calls/r->frames,(double)r->texture_binds/r->frames,
        (double)r->fog_uploads/r->frames,(double)r->command_bytes/r->frames/1024.0,100.0*r->wide_frames/r->frames,r->bottom_ms/r->frames,(unsigned long long)r->asset_reads,(unsigned long long)r->asset_hits,r->asset_bytes/1024.0);
}
static const char* columns="last_game_frame,frames,seconds,fps,worst_ms,over18ms,over25ms,over33_334ms,over50ms,cpu_tick_ms,cpu_submit_ms,gpu_previous_ms,batches_per_frame,vertices_per_frame,texture_hits,texture_misses,upload_kib,audio_queue_drops,stereo_percent,slider_min,slider_max,linear_free_kib,render_wait_ms,render_replay_ms,audio_synth_ms,game_other_ms,draw_calls_per_frame,texture_binds_per_frame,fog_uploads_per_frame,command_kib_per_frame,widescreen_percent,bottom_screen_ms,asset_reads,asset_cache_hits,asset_read_kib\n";
static void writeMenus(const void* data){
    const MenuSnapshot* p=data;
    const struct PerfRow* menus=p->menus;
    FILE* f=fopen(PERF_PATH "/menus.tmp","w");
    if(!f){writeError();return;}
    setvbuf(f,NULL,_IOFBF,8192);
    fprintf(f,"# smash64_menus_v1 build=r8 started_unix=%lld\n# cumulative_this_session=1 scene_entry_frame_excluded=1\nscene,",(long long)time(NULL));
    fputs(columns,f);
    for(unsigned i=0;i<62;i++)if(menus[i].frames){fprintf(f,"%u,",i);writeRow(f,&menus[i]);}
    int ok=!ferror(f);if(fflush(f))ok=0;if(fclose(f))ok=0;
    if(ok){remove(PERF_PATH "/menus.csv");if(rename(PERF_PATH "/menus.tmp",PERF_PATH "/menus.csv"))ok=0;}
    if(!ok)writeError();
    f=fopen(PERF_PATH "/events.tmp","w");if(!f){writeError();return;}
    fprintf(f,"# smash64_events_v1 build=r8 cumulative_this_session=1\n# ids_0_to_61=scene_entry id_62=game_set id_63=stage_preview_change\n");
    fprintf(f,"event,count,mean_ms,worst_ms,cpu_tick_ms,asset_reads,asset_cache_hits,asset_read_kib\n");
    for(unsigned i=0;i<64;i++)if(p->events[i].count){
        const EventRow* e=&p->events[i];
        fprintf(f,"%u,%lu,%.3f,%.3f,%.3f,%llu,%llu,%.2f\n",i,(unsigned long)e->count,
            (double)e->ticks*1000/SYSCLOCK_ARM11/e->count,e->worst_us/1000.0,
            (double)e->work*1000/SYSCLOCK_ARM11/e->count,(unsigned long long)e->reads,(unsigned long long)e->hits,e->bytes/1024.0);
    }
    ok=!ferror(f);if(fflush(f))ok=0;if(fclose(f))ok=0;
    if(ok){remove(PERF_PATH "/events.csv");if(rename(PERF_PATH "/events.tmp",PERF_PATH "/events.csv"))ok=0;}
    if(!ok)writeError();
}
static void finishMenus(void){
    if(!menu_dirty)return;
    MenuSnapshot p;memcpy(p.menus,menus,sizeof(menus));memcpy(p.events,events,sizeof(events));
    if(nativeIoSubmit(writeMenus,&p,sizeof(p),3)==0)menu_dirty=0;else writeError();
}
void nativePerfInit(void) {
    mkdir(PERF_PATH,0777);
    /* Eight tiny reads at startup recover the sequence without an index write. */
    for(unsigned i=0;i<PERF_FILES;i++){
        char path[96];snprintf(path,sizeof(path),PERF_PATH "/match-%u.csv",i);
        FILE* f=fopen(path,"r");unsigned n;
        if(f){if(fscanf(f,"# smash64_perf_v1 sequence=%u",&n)==1&&n>=sequence)sequence=n+1;fclose(f);}
    }
}
void nativePerfResetClock(void) {last_tick=0;menu_last_tick=0;event_tick=0;}
static void writeMatch(const void* data){
    const PerfSnapshot* p=data;
    char path[96],temp[96];unsigned slot=(p->sequence-1)%PERF_FILES;
    snprintf(path,sizeof(path),PERF_PATH "/match-%u.csv",slot);
    snprintf(temp,sizeof(temp),PERF_PATH "/match-%u.tmp",slot);
    FILE* f=fopen(temp,"w");
    if(!f){writeError();return;}
    setvbuf(f,NULL,_IOFBF,16384);
    fprintf(f,"# smash64_perf_v1 sequence=%u build=r8\n# started_unix=%lld reason=%s\n",p->sequence,(long long)p->started,p->reason);
    fprintf(f,"# scene=%lu stage=%lu fighters=%lu;%lu;%lu;%lu kinds=%lu;%lu;%lu;%lu\n",
        (unsigned long)p->match.scene,(unsigned long)p->match.stage,
        (unsigned long)p->match.fighter[0],(unsigned long)p->match.fighter[1],(unsigned long)p->match.fighter[2],(unsigned long)p->match.fighter[3],
        (unsigned long)p->match.kind[0],(unsigned long)p->match.kind[1],(unsigned long)p->match.kind[2],(unsigned long)p->match.kind[3]);
    fprintf(f,"# active_seconds=%.4f frames=%lu average_fps=%.3f worst_ms=%.3f p50_ms_le=%.2f p95_ms_le=%.2f p99_ms_le=%.2f\n",
        (double)p->total.ticks/SYSCLOCK_ARM11,(unsigned long)p->total.frames,
        (double)p->total.frames*SYSCLOCK_ARM11/p->total.ticks,p->total.worst_us/1000.0,percentile(p,50),percentile(p,95),percentile(p,99));
    fprintf(f,"# row_target_seconds=%u pauses_and_countdown_excluded=1 cpu_tick_includes_pacing=1 gpu_is_previous_submission=1\n",p->row_seconds);
    fprintf(f,"# histogram_bin_ms=0.25 final_bin_ge_ms=256 counts=");
    for(unsigned i=0;i<HIST_BINS;i++)fprintf(f,"%s%lu",i?";":"",(unsigned long)p->histogram[i]);
    fputc('\n',f);fputs(columns,f);
    for(unsigned i=0;i<p->row_count;i++)writeRow(f,&p->rows[i]);
    int ok=!ferror(f);if(fflush(f))ok=0;if(fclose(f))ok=0;
    if(ok){remove(path);if(rename(temp,path))ok=0;}
    if(ok)__atomic_fetch_add(&native_perf_saved,1,__ATOMIC_RELAXED);else writeError();
}
void nativePerfFinish(const char* reason){
    finishMenus();
    if(!active)return;
    active=0;last_tick=0;storeRow();if(!total.frames)return;
    PerfSnapshot p;
    memcpy(p.rows,rows,sizeof(rows));p.total=total;p.match=match;
    memcpy(p.histogram,histogram,sizeof(histogram));
    p.row_count=row_count;p.row_seconds=row_seconds;p.sequence=sequence;p.started=started;
    snprintf(p.reason,sizeof(p.reason),"%s",reason);
    if(nativeIoSubmit(writeMatch,&p,sizeof(p),0)==0)sequence++;else writeError();
}
static void accumulate(struct PerfRow* r,uint64_t elapsed,uint64_t work,uint32_t drops,uint32_t frame){
    NativePerfRender* v=&native_perf_render;
    float ms=(float)elapsed*(1000.0f/SYSCLOCK_ARM11);
    if(!r->frames){r->slider_min=v->slider;r->slider_max=v->slider;}
    r->frames++;r->last_frame=frame;r->ticks+=elapsed;r->work_ticks+=work;
    unsigned us=(unsigned)(ms*1000);if(us>r->worst_us)r->worst_us=us;
    r->over18+=ms>18;r->over25+=ms>25;r->over33+=ms>33.334f;r->over50+=ms>50;
    r->submit_ms+=v->submit_ms;r->gpu_ms+=v->gpu_previous_ms;
    r->batches+=v->batches;r->vertices+=v->vertices;r->upload_bytes+=v->upload_bytes;
    r->texture_hits+=v->texture_hits;r->texture_misses+=v->texture_misses;
    r->audio_drops+=drops;r->stereo_frames+=v->eyes==2;
    if(v->slider<r->slider_min)r->slider_min=v->slider;if(v->slider>r->slider_max)r->slider_max=v->slider;
    r->wait_ms+=v->wait_ms;r->replay_ms+=v->replay_ms;r->audio_ms+=v->audio_ms;
    float other=work*(1000.0f/SYSCLOCK_ARM11)-v->render_total_ms-v->audio_ms-v->bottom_ms;
    if(other>0)r->game_ms+=other;
    r->draw_calls+=v->draw_calls;r->texture_binds+=v->texture_binds;
    r->fog_uploads+=v->fog_uploads;r->command_bytes+=v->command_bytes;
    r->wide_frames+=native_widescreen!=0;r->bottom_ms+=v->bottom_ms;
    r->asset_reads+=native_asset_reads;r->asset_hits+=native_asset_hits;r->asset_bytes+=native_asset_bytes;
}
void nativePerfTick(uint64_t now,uint64_t work,uint32_t lists,uint32_t drops) {
    NativePerfGame* g=&native_perf_game;
    unsigned event=64;
    if(g->scene!=event_scene&&g->scene<62)event=g->scene;
    else if(g->in_match&&g->status>=5&&event_status<5)event=62;
    else if(g->scene==21&&g->stage!=event_stage)event=63;
    if(event<64&&event_tick){
        EventRow* e=&events[event];uint64_t elapsed=now-event_tick;
        uint32_t us=elapsed*1000000/SYSCLOCK_ARM11;
        e->count++;e->ticks+=elapsed;e->work+=work;
        if(us>e->worst_us)e->worst_us=us;
        e->reads+=native_asset_reads;e->hits+=native_asset_hits;e->bytes+=native_asset_bytes;menu_dirty=1;
    }
    event_tick=now;event_scene=g->scene;event_stage=g->stage;event_status=g->status;
    if(active&&(!g->in_match||g->scene!=match.scene||g->stage!=match.stage||g->status>=5))nativePerfFinish("match_end");
    if(!g->in_match&&g->scene<62){
        if(menu_last_tick&&menu_last_scene==g->scene&&lists!=menu_last_lists){
            struct PerfRow* r=&menus[g->scene];
            accumulate(r,now-menu_last_tick,work,drops-menu_last_drops,lists);menu_dirty=1;
            if(!r->linear_min||lists%60==0)r->linear_min=linearSpaceFree();
        }
        menu_last_tick=now;menu_last_scene=g->scene;menu_last_lists=lists;menu_last_drops=drops;
    }else menu_last_tick=0;
    if(!g->in_match||g->status!=1){last_tick=0;return;}
    if(!active){
        match=*g;active=1;started=time(NULL);row_count=0;row_seconds=1;
        memset(&current,0,sizeof(current));memset(&total,0,sizeof(total));memset(histogram,0,sizeof(histogram));
        last_tick=0;
    }
    if(!last_tick){last_tick=now;last_lists=lists;last_drops=drops;return;}
    if(lists==last_lists)return;
    uint64_t elapsed=now-last_tick;last_tick=now;last_lists=lists;
    float ms=(float)elapsed*(1000.0f/SYSCLOCK_ARM11);
    unsigned bin=(unsigned)(ms*4);if(bin>=HIST_BINS)bin=HIST_BINS-1;histogram[bin]++;
    accumulate(&current,elapsed,work,drops-last_drops,g->game_frame);last_drops=drops;
    if(current.ticks>=(uint64_t)row_seconds*SYSCLOCK_ARM11)storeRow();
}

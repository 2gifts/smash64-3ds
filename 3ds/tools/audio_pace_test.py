"""Host simulation of audio pacing against a 32 kHz DSP queue.

Compares the original fixed pacing (exactly 1/60 s per game tic) with the
queue-driven pacing in src/audio_pace.c across realistic frame timings, and
fails if the new pacing is not gap-free where it can be.
"""
import json
import subprocess
from build import ROOT, OUT, BIN

HARNESS = r'''
#include <stdio.h>
#include <string.h>
#include "native_audio.h"
#define RATE 32000
#define BUFFERS 6
/* The original port pacing: 552 or 368 samples, averaging RATE/60 per tic. */
static int fixedPace(int* error){
    int high=552,low=368,step=high*60-RATE,limit=(high-low)*60;
    *error+=step;if(*error>=limit){*error-=limit;return low;}return high;
}
typedef struct {double t;double queue;double slots[BUFFERS];int count;long gaps;double starved;long ticks;} Dsp;
/* Play until time t; whole buffers retire from the front of the queue. */
static void play(Dsp* d,double t){
    double need=(t-d->t)*RATE;d->t=t;
    while(need>0&&d->count){
        double take=need<d->slots[0]?need:d->slots[0];
        d->slots[0]-=take;need-=take;d->queue-=take;
        if(d->slots[0]<=0){memmove(d->slots,d->slots+1,(--d->count)*sizeof(double));}
    }
    if(need>0.5){d->gaps++;d->starved+=need;}
}
static void submit(Dsp* d,int n){if(d->count<BUFFERS){d->slots[d->count++]=n;d->queue+=n;}}
/* Frame times in ms for one scenario; returns the time of tic i. */
static double scenario(int kind,long i){
    switch(kind){
    case 0:return i*1000.0/59.8261;                                  /* every vblank */
    case 1:return i*1000.0/59.8261+(i/8)*16.715;                      /* a dropped frame every 8 */
    case 2:return i*1000.0/45.0;                                      /* steady 45 fps */
    case 3:return i*1000.0/36.0;                                      /* steady 36 fps */
    default:{                                                         /* 5 s at 60, 5 s at 40 */
        double t=0;for(long k=0;k<i;k++)t+=((k/300)%2)?25.0:16.715;return t;}
    }
}
int main(void){
    const char* names[]={"vblank_59_83","drop_every_8","fps_45","fps_36","alternate_60_40"};
    printf("[");
    for(int kind=0;kind<5;kind++){
        for(int mode=0;mode<2;mode++){
            Dsp d={0};NativeAudioPace pace={0};int error=0;
            long tics=kind==4?6000:3600;
            for(long i=0;i<tics;i++){
                double t=scenario(kind,i)/1000.0;
                if(i)play(&d,t);else d.t=t;
                int n=mode?nativeAudioPace(&pace,(int)d.queue,RATE):fixedPace(&error);
                submit(&d,n);d.ticks++;
            }
            printf("%s{\"scenario\":\"%s\",\"pacing\":\"%s\",\"gaps\":%ld,\"starved_ms\":%.1f,\"final_queue\":%.0f}",
                kind||mode?",":"",names[kind],mode?"queue":"fixed",d.gaps,d.starved*1000.0/RATE,d.queue);
        }
    }
    printf("]\n");
}
'''


def main():
    d = OUT/'audio-pace-host'
    d.mkdir(parents=True, exist_ok=True)
    (d/'test.c').write_text(HARNESS)
    exe = d/'test.exe'
    p = subprocess.run([str(BIN/'clang.exe'), '-O2', '-I'+str(ROOT/'include'), str(d/'test.c'),
                        str(ROOT/'src/audio_pace.c'), '-o', str(exe)], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    rows = json.loads(subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout)
    for r in rows:
        print(f"{r['scenario']:>16} {r['pacing']:>6}: gaps={r['gaps']:5d} starved={r['starved_ms']:8.1f} ms queue={r['final_queue']:.0f}")
    by = {(r['scenario'], r['pacing']): r for r in rows}
    # Queue pacing must be gap-free whenever five chunks per tic can keep up
    # (down to about 35 tics per second), and never worse than fixed pacing.
    for name in ('vblank_59_83', 'drop_every_8', 'fps_45', 'fps_36', 'alternate_60_40'):
        assert by[(name, 'queue')]['gaps'] <= 2, by[(name, 'queue')]
        assert by[(name, 'queue')]['starved_ms'] <= by[(name, 'fixed')]['starved_ms'], name
    (d/'verified.json').write_text(json.dumps(rows, indent=2))
    print('audio pacing simulation passed')


if __name__ == '__main__':
    main()

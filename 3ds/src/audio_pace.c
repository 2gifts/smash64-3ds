#include "native_audio.h"
/* The top screen refreshes at about 59.83 Hz and slow frames delay tics, so
 * the original fixed size (exactly 1/60 s) slowly drained the DSP queue and
 * every hitch then became an audible gap. Each frame now replaces what the
 * DSP played since the previous tic (smoothed) and steers the queue toward
 * three frames. Synthesis advances music by the samples it produces, so
 * tempo stays correct while the game itself runs slower than 60 tics. */
int32_t nativeAudioPace(NativeAudioPace* p,int32_t queued,int32_t rate){
    const int32_t frame=rate/60,target=frame*3;
    if(!p->started){p->started=1;p->played=frame;p->lastQueued=-1;}
    if(p->lastQueued>=0){
        int32_t consumed=p->lastQueued+p->lastMade-queued;
        if(consumed>0&&consumed<rate/4)p->played+=(consumed-p->played)*0.25f;
    }
    int32_t want=(int32_t)p->played+(target-queued)/2;
    int32_t chunks=(want+AUDIO_CHUNK_SAMPLES/2)/AUDIO_CHUNK_SAMPLES;
    if(chunks<2)chunks=2;
    if(chunks>AUDIO_MAX_CHUNKS)chunks=AUDIO_MAX_CHUNKS;
    p->lastQueued=queued;p->lastMade=chunks*AUDIO_CHUNK_SAMPLES;
    return p->lastMade;
}

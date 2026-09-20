#include <sys/obj.h>
#include <math.h>
#include <stdint.h>
#include <stdbool.h>
/* The engine records camera parameters while building its display list. The
 * renderer uses that immutable snapshot when it later consumes each matrix. */
static struct CameraSample {const void* matrix;float focus_w;int perspective;} samples[256];
static unsigned nextSample;
float native_stereo_focus_w;
int native_stereo_perspective;
static float matrixW(const void* matrix,unsigned row) {
    /* N64 matrices split signed 16.16 values into two 32-byte halves. Only
     * column W is needed, once per camera, not once per vertex or eye. */
    const uint32_t* words=matrix;
    return (int32_t)((words[row*2+1]<<16)|(words[row*2+9]&0xffff))/65536.0f;
}
void portInterpRecordMtx(void* matrix,void* owner,int ordinal,int tag) {
    if(tag!=1)return;
    CObj* camera=owner;
    if(ordinal<0||ordinal>=camera->xobjs_num||!camera->xobjs[ordinal])return;
    int kind=camera->xobjs[ordinal]->kind;
    bool separatePerspective=kind==nGCMatrixKindPerspFastF||kind==nGCMatrixKindPerspF;
    /* Gameplay uses custom kind 0x4c: a combined view/projection matrix.
     * Classify custom camera matrices from W so orthographic magnifiers and
     * HUD cameras stay flat. Ordinary look-at MUL commands retain the prior
     * projection's focus and must not create a new projection sample. */
    if(!separatePerspective&&kind!=nGCMatrixKindOrtho&&kind<66)return;
    struct CameraSample* sample=NULL;
    for(unsigned i=0;i<256;i++)if(samples[i].matrix==matrix){sample=&samples[i];break;}
    if(!sample)sample=&samples[nextSample++%256];
    float wx=matrixW(matrix,0),wy=matrixW(matrix,1),wz=matrixW(matrix,2);
    sample->matrix=matrix;sample->focus_w=0;
    sample->perspective=separatePerspective||(kind>=66&&(wx!=0||wy!=0||wz!=0));
    if(sample->perspective) {
        if(separatePerspective){
            float x=camera->vec.eye.x-camera->vec.at.x;
            float y=camera->vec.eye.y-camera->vec.at.y;
            float z=camera->vec.eye.z-camera->vec.at.z;
            sample->focus_w=sqrtf(x*x+y*y+z*z)*fabsf(wz);
        }else{
            /* The match camera rescales its projection dynamically. Evaluating
             * the actual emitted matrix at the focus point includes that scale. */
            sample->focus_w=wx*camera->vec.at.x+wy*camera->vec.at.y+wz*camera->vec.at.z+matrixW(matrix,3);
        }
    }
}
int nativeStereoLoadProjection(const void* matrix) {
    native_stereo_focus_w=0;native_stereo_perspective=0;
    for(unsigned i=0;i<256;i++)if(samples[i].matrix==matrix){
        native_stereo_focus_w=samples[i].focus_w;
        native_stereo_perspective=samples[i].perspective&&samples[i].focus_w>0.0f;
        break;
    }
    return native_stereo_perspective;
}

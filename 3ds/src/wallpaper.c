#include <gr/ground.h>
#include <sc/scene.h>
#include "native_display.h"
#include "native_stereo.h"
extern GObj* sGRWallpaperGObj;
extern void __real_lbCommonDrawSObjAttr(GObj*);
void __wrap_lbCommonDrawSObjAttr(GObj* gobj){
    unsigned scene=gSCManagerSceneData.scene_curr;
    int match=scene==nSCKindVSBattle||scene==nSCKind1PGame||scene==nSCKind1PBonusStage||scene==nSCKind1PTrainingMode;
    if(match&&gobj==sGRWallpaperGObj){
        SObj* s=SObjGetStruct(gobj);
        float sx=s->sprite.scalex,sy=s->sprite.scaley,x=s->pos.x,y=s->pos.y;
        /* The original backdrop is a photograph-like 300x220 sprite, not
         * world geometry. Cover the viewport with uniform scaling and crop
         * excess height in wide, rather than stretching mountains/clouds. */
        if(native_widescreen){s->sprite.scaley*=11.0f/9.0f;s->pos.y=120+(y-120)*(11.0f/9.0f);}
        Gfx* marker=gSYTaskmanDLHeads[0]++;
        gSPNoOp(marker);marker->words.w1=NATIVE_BACKDROP_BEGIN;
        __real_lbCommonDrawSObjAttr(gobj);
        marker=gSYTaskmanDLHeads[0]++;
        gSPNoOp(marker);marker->words.w1=NATIVE_BACKDROP_END;
        s->sprite.scalex=sx;s->sprite.scaley=sy;s->pos.x=x;s->pos.y=y;
    }else __real_lbCommonDrawSObjAttr(gobj);
}

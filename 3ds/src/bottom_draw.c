/* CPU compositor. Original sprites are cached once; no PICA state, texture
 * uploads, scene-arena pointers, or filesystem reads occur during drawing. */
#include "native_bottom.h"
#include "bottom_art_ids.h"
#include "native_perf.h"
#include "native_controls.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define RGB(r,g,b) ((((r)>>3)<<11)|(((g)>>2)<<5)|((b)>>3))
static const uint16_t paper=RGB(244,237,213),gold=RGB(248,198,62),muted=RGB(167,165,151);
static const uint16_t colors[4]={RGB(235,68,63),RGB(75,140,235),RGB(241,190,43),RGB(65,188,105)};
static const char* names[12]={"MARIO","FOX","DONKEY KONG","SAMUS","LUIGI","LINK","YOSHI","C. FALCON","KIRBY","PIKACHU","JIGGLYPUFF","NESS"};
static const char* stages[9]={"PEACH'S CASTLE","SECTOR Z","KONGO JUNGLE","PLANET ZEBES","HYRULE CASTLE","YOSHI'S ISLAND","DREAM LAND","SAFFRON CITY","MUSHROOM KINGDOM"};
typedef struct {uint32_t w,h,offset;} Art;
typedef struct {uint16_t color;uint8_t alpha,pad;} Pixel;
static unsigned char* art;
static Art* sprites;
static uint16_t* canvas;
static uint16_t backdrop[320*240];
static unsigned backdropReady;
static uint16_t blend(uint16_t a,uint16_t b,unsigned alpha){
    unsigned rb=(((a&0xf81f)*alpha+(b&0xf81f)*(32-alpha))>>5)&0xf81f;
    unsigned g=(((a&0x07e0)*alpha+(b&0x07e0)*(32-alpha))>>5)&0x07e0;return rb|g;
}
static void pixel(int x,int y,uint16_t c,unsigned a){
    if((unsigned)x<320&&(unsigned)y<240){uint16_t* p=canvas+x*240+239-y;*p=a>=32?c:blend(c,*p,a);}
}
static void rect(int x,int y,int w,int h,uint16_t c){
    int ex=x+w,ey=y+h;if(x<0)x=0;if(y<0)y=0;if(ex>320)ex=320;if(ey>240)ey=240;
    for(int xx=x;xx<ex;xx++){uint16_t* p=canvas+xx*240+240-ey;for(int yy=y;yy<ey;yy++)*p++=c;}
}
static void image(unsigned id,int x,int y,int w,int h,int tint,unsigned opacity){
    if(!art||id>=BART_COUNT||w<=0||h<=0)return;
    const Art* s=&sprites[id];const Pixel* pixels=(const Pixel*)(art+s->offset);
    unsigned cols[320];if(w>320)w=320;
    for(int xx=0;xx<w;xx++)cols[xx]=xx*s->w/w;
    for(int yy=0;yy<h;yy++)for(int xx=0;xx<w;xx++){
        Pixel p=pixels[(yy*s->h/h)*s->w+cols[xx]];unsigned a=p.alpha*opacity/32;
        if(a)pixel(x+xx,y+yy,tint<0?p.color:tint,a);
    }
}
int nativeBottomArtInit(const char* path){
    FILE* f=fopen(path,"rb");if(!f)return 0;
    fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    if(n<8+BART_COUNT*12||n>1024*1024){fclose(f);return 0;}
    art=malloc(n);if(!art){fclose(f);return 0;}
    int ok=fread(art,1,n,f)==(size_t)n;fclose(f);
    if(!ok||memcmp(art,"BUI1",4)||*(uint32_t*)(art+4)!=BART_COUNT)goto bad;
    sprites=(Art*)(art+8);
    for(unsigned i=0;i<BART_COUNT;i++){
        Art* a=&sprites[i];if(!a->w||!a->h||a->w>320||a->h>240||a->offset>n||a->w*a->h*4>(unsigned)n-a->offset)goto bad;
    }
    backdropReady=0;return 1;
bad:free(art);art=NULL;sprites=NULL;return 0;
}
void nativeBottomArtExit(void){free(art);art=NULL;sprites=NULL;backdropReady=0;}
static unsigned glyph(unsigned ch){
    if(ch>='a'&&ch<='z')ch-=32;
    if(ch>='A'&&ch<='Z')return BART_FONT_A+ch-'A';
    if(ch>='0'&&ch<='9')return BART_FONT_0+ch-'0';
    if(ch=='%')return BART_FONT_PERCENT;if(ch=='.')return BART_FONT_PERIOD;
    if(ch=='\'')return BART_FONT_APOSTROPHE;return BART_COUNT;
}
static int advance(unsigned ch,int h){
    if(ch=='.'||ch=='\'')return h/3+1;
    unsigned id=glyph(ch);if(ch==' ')return h/2;
    return id<BART_COUNT&&sprites?(sprites[id].w*h+sprites[id].h/2)/sprites[id].h+1:h/2+1;
}
static int width(const char* s,int h){int n=0;for(;*s;s++)n+=advance((unsigned char)*s,h);return n?n-1:0;}
static void text(int x,int y,const char* s,int h,uint16_t c){
    for(;*s;s++){
        unsigned ch=(unsigned char)*s,id=glyph(ch);int w=advance(ch,h)-1;
        if(ch=='.')rect(x,y+h-(h/5+1),h/5+1,h/5+1,c);
        else if(ch=='\'')rect(x,y,h/5+1,h/3+1,c);
        else if(id<BART_COUNT){image(id,x+1,y+1,w,h,0,24);image(id,x,y,w,h,c,32);}
        else if(ch==':'){rect(x+1,y+h/4,2,2,c);rect(x+1,y+3*h/4,2,2,c);}
        else if(ch=='-'||ch=='+'){rect(x,y+h/2,w,1,c);if(ch=='+')rect(x+w/2,y+h/4,1,h/2+1,c);}
        else if(ch=='/')for(int i=0;i<h;i++)pixel(x+w-1-i*w/h,y+i,c,32);
        x+=w+1;
    }
}
static void fit(int x,int y,const char* s,int h,int maxw,uint16_t c){while(h>6&&width(s,h)>maxw)h--;text(x,y,s,h,c);}
static void right(int x,int y,const char* s,int h,uint16_t c){text(x-width(s,h),y,s,h,c);}
static void center(int x,int y,const char* s,int h,uint16_t c){text(x-width(s,h)/2,y,s,h,c);}
static void plate(int x,int y,int w,int h,uint16_t c){
    rect(x,y,w,h,c);rect(x,y,w,1,RGB(127,122,108));rect(x,y,1,h,RGB(98,94,85));
    rect(x+w-1,y+1,1,h-1,RGB(12,12,12));rect(x+1,y+h-1,w-1,1,RGB(8,8,8));
}
static unsigned fighterArt(unsigned c){return c==13?0:c==26?2:c>=14&&c<26?c-14:c;}
static const char* fighterName(unsigned c){return c==12?"MASTER HAND":c==13?"METAL MARIO":c==26?"GIANT DK":c>=14&&c<26?"POLYGON":c<12?names[c]:"SELECT";}
static void background(void){
    if(backdropReady){memcpy(canvas,backdrop,sizeof(backdrop));return;}
    rect(0,0,320,240,RGB(29,29,27));
    if(art){Art* s=&sprites[BART_STONE];for(unsigned x=0;x<320;x+=s->w)for(unsigned y=0;y<240;y+=s->h)image(BART_STONE,x,y,s->w,s->h,-1,4);}
    memcpy(backdrop,canvas,sizeof(backdrop));backdropReady=1;
}
static void header(const char* title,const char* side){
    rect(0,0,320,29,RGB(24,24,22));rect(0,29,320,2,gold);
    for(int y=0;y<29;y++)rect(0,y,5+(28-y)/4,1,RGB(165,41,34));
    fit(18,9,title,12,214,paper);right(309,10,side,10,gold);
}
static void footer(unsigned fps,unsigned wide,unsigned page){
    static const int x[3]={5,108,211};
    for(unsigned i=0;i<3;i++)plate(x[i],212,104,25,page==i+1?RGB(84,68,32):RGB(53,52,46));
    char b[24];snprintf(b,sizeof(b),fps?"%u.%u FPS":"--.- FPS",fps/10,fps%10);
    center(57,221,b,8,page==BOTTOM_PERFORMANCE?gold:paper);
    center(160,221,wide?"VIEW: WIDE":"VIEW: 4:3",8,paper);
    center(263,221,page==BOTTOM_CONTROLS||page==BOTTOM_GUIDE?"BACK":"CONTROLS",8,page==BOTTOM_CONTROLS||page==BOTTOM_GUIDE?gold:paper);
}
unsigned nativeBottomHit(unsigned x,unsigned y){return x>=320||y<212||y>=240?BOTTOM_NONE:x<108?BOTTOM_PERFORMANCE:x<212?BOTTOM_DISPLAY:BOTTOM_CONTROLS;}
unsigned nativeBottomControlsHit(unsigned x,unsigned y){
    if(x<8||x>=312)return BOTTOM_NONE;
    return y>=40&&y<90?BOTTOM_TAP_JUMP:y>=98&&y<148?BOTTOM_CSTICK:y>=166&&y<196?BOTTOM_GUIDE:BOTTOM_NONE;
}
static void damage(int x,int y,unsigned n,int h,unsigned hp,int dim){
    char b[16];snprintf(b,sizeof(b),"%u",n>999?999:n);int total=0;
    for(const char* s=b;*s;s++){Art* a=&sprites[BART_DAMAGE_0+*s-'0'];total+=a->w*h/a->h;}
    int ph=h*2/3,pw=sprites[BART_DAMAGE_PERCENT].w*ph/sprites[BART_DAMAGE_PERCENT].h;
    total+=hp?width("HP",10)+2:pw;x-=total;
    int tint=dim?muted:(hp?n<=50:n>=150)?RGB(245,93,76):(hp?n<=100:n>=100)?gold:paper;
    for(const char* s=b;*s;s++){unsigned id=BART_DAMAGE_0+*s-'0';Art* a=&sprites[id];int w=a->w*h/a->h;
        image(id,x+1,y+1,w,h,0,32);image(id,x,y,w,h,tint,32);x+=w;}
    if(hp)text(x+2,y+h-10,"HP",10,paper);else image(BART_DAMAGE_PERCENT,x,y+h-ph,pw,ph,tint,32);
}
static void card(int x,int y,int w,int h,const NativeBottomPlayer* p,unsigned slot,unsigned page,unsigned training){
    unsigned active=p->kind<2,valid=fighterArt(p->character)<12;
    int out=page==BOTTOM_BATTLE&&p->stock_limited&&!p->stocks;
    uint16_t color=active?colors[p->color%4]:muted;
    plate(x,y,w,h,active?RGB(54,54,48):RGB(36,36,33));
    rect(x+1,y+1,w-2,18,active?blend(color,RGB(15,15,14),15):RGB(47,47,43));
    rect(x+1,y+19,w-2,1,color);char b[48];
    if(active&&page==BOTTOM_BATTLE&&p->combo_hits>=2){
        snprintf(b,sizeof(b),"%u HIT COMBO",p->combo_hits);fit(x+7,y+6,b,9,w-34,p->combo_active?gold:paper);
    }else fit(x+7,y+6,active?fighterName(p->character):"NO ENTRY",9,w-42,out?muted:paper);
    snprintf(b,sizeof(b),"%uP",slot+1);right(x+w-6,y+6,b,9,color);
    if(!active){center(x+w/2,y+38,"CLOSED",10,muted);return;}
    int large=w>200,pw=45,ph=43,px=x+6,py=y+25;
    if(valid)image(BART_PORTRAIT_MARIO+fighterArt(p->character),px,py,pw,ph,-1,out?11:32);
    else{image(BART_LOGO,px,py,pw,ph,muted,24);}
    int tx=x+pw+13;
    if(page==BOTTOM_BATTLE&&art){
        if(out)right(x+w-9,y+29,"OUT",18,muted);
        else damage(x+w-8,y+25,p->damage,large?34:27,p->character==12,0);
    }else if(page==BOTTOM_RESULTS){
        static const char* ranks[]={"","1ST","2ND","3RD","4TH"};
        right(x+w-8,y+27,ranks[p->place<=4?p->place:0],large?24:18,p->place==1?gold:paper);
    }else{
        fit(tx,y+28,p->ready?"READY":"CHOOSING",large?15:10,w-(tx-x)-7,p->ready?gold:muted);
    }
    if(page==BOTTOM_BATTLE&&p->stock_limited){
        unsigned n=p->stocks;int cy=y+h-15;
        if(valid&&n<=5&&n>0){for(unsigned i=0;i<n;i++)image(BART_STOCK_MARIOMODEL+fighterArt(p->character),tx+i*13,cy-1,11,11,-1,32);}
        else{snprintf(b,sizeof(b),"STOCK %u",n);text(tx,cy,b,8,out?muted:paper);}
    }else if(page==BOTTOM_BATTLE&&!training||page==BOTTOM_RESULTS){
        snprintf(b,sizeof(b),"KO %d / FALL %d",p->kos,p->falls);fit(tx,y+h-14,b,8,w-(tx-x)-5,muted);
    }else{
        snprintf(b,sizeof(b),p->kind==1?"CPU LV %u":"HUMAN",p->level);text(tx,y+h-15,b,8,paper);
    }
}
static const char* menuTitle(unsigned scene){
    switch(scene){case 7:return "SMASH BROS.";case 8:return "1P MODE";case 9:return "VS MODE";
    case 10:return "VS OPTIONS";case 11:return "ITEM SWITCH";case 13:return "CHALLENGER";
    case 25:return "VS RECORDS";case 26:return "CHARACTER DATA";case 56:return "STAFF ROLL";
    case 57:return "OPTIONS";case 58:return "DATA";case 59:return "SOUND TEST";
    default:return "SMASH BROS.";}
}
static void controls(void){
    header("CONTROL OPTIONS","1P");
    plate(8,40,304,50,RGB(39,39,35));
    text(18,49,"TAP JUMP",12,paper);right(302,49,native_tap_jump_disabled?"OFF":"ON",12,gold);
    text(18,73,native_tap_jump_disabled?"X / Y JUMP. UP DOES NOT JUMP.":"CIRCLE PAD UP OR X / Y TO JUMP.",8,muted);
    plate(8,98,304,50,RGB(39,39,35));
    text(18,107,"C-STICK",12,paper);right(302,107,native_cstick_enabled?"SMASH":"OFF",12,gold);
    text(18,131,"GROUND SMASHES / DIRECTIONAL AERIALS",7,muted);
    plate(8,166,304,30,RGB(39,39,35));center(160,175,"BUTTON GUIDE",10,paper);
    center(160,201,"TAP AN OPTION TO CHANGE. AUTO SAVED.",7,muted);
}
static void guide(void){
    header("HOW TO PLAY","CONTROLS");
    const char* key[]={"CIRCLE PAD","A","B","X / Y","L / R","ZL / ZR","D-PAD UP","START","SELECT"};
    const char* action[]={native_tap_jump_disabled?"MOVE":"MOVE / UP TO JUMP","ATTACK","SPECIAL MOVE","JUMP","SHIELD","GRAB","TAUNT","PAUSE","SAVE REPORT / EXIT"};
    plate(8,40,304,160,RGB(39,39,35));
    for(unsigned i=0;i<9;i++){int y=48+i*16;text(18,y,key[i],8,gold);text(139,y,action[i],8,paper);}
}
static void performance(unsigned fps,unsigned reports,unsigned errors){
    header("PERFORMANCE","LIVE");char b[64];
    snprintf(b,sizeof(b),"%u.%u FPS",fps/10,fps%10);center(160,47,b,22,paper);
    const char* labels[]={"CPU RENDER","PREVIOUS GPU","BOTTOM SCREEN","DRAW CALLS"};
    float values[]={native_perf_render.submit_ms,native_perf_render.gpu_previous_ms,native_bottom_last_ms,0};
    for(unsigned i=0;i<4;i++){int y=83+i*20;text(17,y,labels[i],9,muted);
        if(i==3)snprintf(b,sizeof(b),"%u",native_perf_render.draw_calls);else snprintf(b,sizeof(b),"%.2f MS",values[i]);
        right(303,y,b,9,paper);}
    snprintf(b,sizeof(b),errors?"REPORT WRITE FAILED":"REPORTS SAVED: %u",reports);text(17,172,b,9,errors?colors[0]:gold);
    text(17,190,"LATEST 8 MATCHES KEPT ON SD",8,muted);
}
void nativeBottomDraw(uint16_t* target,const NativeBottomState* s,unsigned fps,unsigned wide,unsigned page,unsigned reports,unsigned errors,unsigned audio){
    canvas=target;background();
    if(page==BOTTOM_CONTROLS)controls();
    else if(page==BOTTOM_GUIDE)guide();
    else if(page==BOTTOM_PERFORMANCE)performance(fps,reports,errors);
    else if(s->page!=BOTTOM_MENU){
        const char* title=s->page==BOTTOM_SELECT?"SELECT FIGHTERS":s->page==BOTTOM_STAGE?"SELECT STAGE":s->page==BOTTOM_RESULTS?"RESULTS":s->training?"TRAINING":s->bonus?"BONUS GAME":s->sudden_death?"SUDDEN DEATH":s->teams?"TEAM BATTLE":"FREE-FOR-ALL";
        char side[32];
        if(s->page==BOTTOM_BATTLE){
            if(s->status==2||s->status==3)strcpy(side,"PAUSED");
            else if(s->status>=5)strcpy(side,"GAME SET");
            else if(s->status==0)strcpy(side,"READY");
            else if(s->training)side[0]=0;
            else if(s->timer||s->bonus)snprintf(side,sizeof(side),"%u:%02u",s->seconds/60,s->seconds%60);
            else strcpy(side,s->stock_mode?"STOCK":"NO LIMIT");
        }else if(s->stock_mode)snprintf(side,sizeof(side),"%u STOCK",s->rule_stocks);
        else if(s->rule_minutes&&s->rule_minutes<100)snprintf(side,sizeof(side),"%u MIN",s->rule_minutes);
        else strcpy(side,s->training?"PRACTICE":"");
        header(title,side);
        unsigned slots[4],n=0;for(unsigned i=0;i<4;i++)if(s->players[i].kind<2)slots[n++]=i;
        if(s->page==BOTTOM_SELECT&&s->scene==16){n=4;for(unsigned i=0;i<4;i++)slots[i]=i;}
        if(n<=2){for(unsigned j=0;j<n;j++)card(8,40+j*79,304,73,&s->players[slots[j]],slots[j],s->page,s->training);}
        else for(unsigned j=0;j<4;j++)card(8+(j%2)*156,40+(j/2)*79,148,73,&s->players[j],j,s->page,s->training);
        if(s->page==BOTTOM_BATTLE&&s->stage<9)center(160,201,stages[s->stage],7,muted);
        else if(s->page==BOTTOM_SELECT)center(160,201,"A SELECT  /  B BACK  /  START READY",7,muted);
        else if(s->page==BOTTOM_STAGE)center(160,201,"CHOOSE A STAGE ON THE TOP SCREEN",7,muted);
    }else{
        header(menuTitle(s->scene),"NINTENDO 64");
        image(BART_LOGO,111,44,98,98,gold,28);
        center(160,154,s->status==~0u?"LOADING GAME":s->scene==1||s->scene>=27&&s->scene<=45?"PRESS START":"A SELECT   /   B BACK",12,paper);
        center(160,181,"3D SLIDER ADJUSTS DEPTH",8,muted);
    }
    if(errors){rect(0,198,320,12,RGB(88,34,23));center(160,201,"SD WRITE FAILED / TAP FPS",7,gold);}
    if(!audio){rect(0,198,320,12,RGB(88,34,23));center(160,201,"AUDIO NEEDS /3DS/DSPFIRM.CDC",7,gold);}
    footer(fps,wide,page);
}

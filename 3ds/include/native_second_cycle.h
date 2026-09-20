static uint32_t nativeCycleWords[2],nativeCycleMode,nativeCycleEnv,nativeCyclePrim;
int native_second_needs_shade;
void nativeSetSecondCycle(uint32_t a,uint32_t b,uint32_t mode,uint32_t env,uint32_t prim) {
    nativeCycleWords[0]=a;nativeCycleWords[1]=b;nativeCycleMode=mode;nativeCycleEnv=env;
    nativeCyclePrim=prim;
    native_second_needs_shade=((mode>>20)&3)==1&&((a&31)==4||(a&31)==12);
}
static void nativeApplyFirstCycle(bool useAlpha,unsigned inputs) {
    uint32_t w0=nativeCycleWords[0],w1=nativeCycleWords[1];
    unsigned a=(w0>>20)&15,b=(w1>>28)&15,c=(w0>>15)&31,d=(w1>>15)&7;
    if(inputs>2&&a==3&&b==5&&c==1&&d==5){
        /* Yoshi's Island blends two constant colors by a texture, then lights
         * that result in cycle two. Reserve the vertex color for that lighting. */
        C3D_TexEnv* e0=C3D_GetTexEnv(0);C3D_TexEnvInit(e0);
        C3D_TexEnvColor(e0,nativeCycleEnv);
        C3D_TexEnvSrc(e0,C3D_RGB,GPU_CONSTANT,GPU_CONSTANT,GPU_CONSTANT);
        C3D_TexEnvFunc(e0,C3D_RGB,GPU_REPLACE);
        C3D_TexEnv* e1=C3D_GetTexEnv(1);C3D_TexEnvInit(e1);
        C3D_TexEnvColor(e1,useAlpha?nativeCyclePrim:nativeCyclePrim|0xff000000u);
        C3D_TexEnvSrc(e1,C3D_RGB,GPU_CONSTANT,GPU_PREVIOUS,GPU_TEXTURE0);
        C3D_TexEnvFunc(e1,C3D_RGB,GPU_INTERPOLATE);
        unsigned aa=(w0>>12)&7,ab=(w1>>12)&7,ac=(w0>>9)&7,ad=(w1>>9)&7;
        if(useAlpha){
            if(aa==1&&ab==7&&ac==3&&ad==7){
                C3D_TexEnvFunc(e1,C3D_Alpha,GPU_MODULATE);
                C3D_TexEnvSrc(e1,C3D_Alpha,GPU_TEXTURE0,GPU_CONSTANT,GPU_CONSTANT);
            }else if((aa==ab||ac==7)&&ad==1){
                C3D_TexEnvFunc(e1,C3D_Alpha,GPU_REPLACE);
                C3D_TexEnvSrc(e1,C3D_Alpha,GPU_TEXTURE0,GPU_CONSTANT,GPU_CONSTANT);
            }else{port_log("Unsupported constant-blend alpha %08x %08x\n",w0,w1);abort();}
        }else{
            C3D_TexEnvFunc(e1,C3D_Alpha,GPU_REPLACE);
            C3D_TexEnvSrc(e1,C3D_Alpha,GPU_CONSTANT,GPU_CONSTANT,GPU_CONSTANT);
        }
    }else if(inputs>2){port_log("Unsupported first-cycle inputs %08x %08x count=%u\n",w0,w1,inputs);abort();}
}
static void nativeApplySecondCycle(void) {
    C3D_TexEnv* e=C3D_GetTexEnv(2);C3D_TexEnvInit(e);
    C3D_TexEnv* alpha=C3D_GetTexEnv(3);C3D_TexEnvInit(alpha);
    if(((nativeCycleMode>>20)&3)!=1)return;
    uint32_t w0=nativeCycleWords[0],w1=nativeCycleWords[1];
    unsigned a=(w0>>5)&15,b=(w1>>24)&15,c=w0&31,d=(w1>>6)&7;
    C3D_TexEnvColor(e,nativeCycleEnv);
    if(a==0&&b==15&&c==5&&d==7){
        C3D_TexEnvFunc(e,C3D_RGB,GPU_MODULATE);
        C3D_TexEnvSrc(e,C3D_RGB,GPU_PREVIOUS,GPU_CONSTANT,GPU_PRIMARY_COLOR);
    } else if(a==0&&b==15&&c==4&&d==7){
        C3D_TexEnvFunc(e,C3D_RGB,GPU_MODULATE);
        C3D_TexEnvSrc(e,C3D_RGB,GPU_PREVIOUS,GPU_PRIMARY_COLOR,GPU_CONSTANT);
    } else if(a==5&&b==0&&c==12&&d==0){
        C3D_TexEnvFunc(e,C3D_RGB,GPU_INTERPOLATE);
        C3D_TexEnvSrc(e,C3D_RGB,GPU_CONSTANT,GPU_PREVIOUS,GPU_PRIMARY_COLOR);
        C3D_TexEnvOpRgb(e,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_ALPHA);
    } else if(!((a==b||c==31)&&d==0)){
        port_log("Unsupported second RGB cycle %08x %08x\n",w0,w1);abort();
    }
    a=(w1>>21)&7;b=(w1>>3)&7;c=(w1>>18)&7;d=w1&7;
    if(a==0&&b==7&&(c==5||c==3||c==4)&&d==7){
        C3D_TexEnvColor(alpha,c==5?nativeCycleEnv:nativeCyclePrim);
        C3D_TexEnvFunc(alpha,C3D_Alpha,GPU_MODULATE);
        C3D_TexEnvSrc(alpha,C3D_Alpha,GPU_PREVIOUS,c==4?GPU_PRIMARY_COLOR:GPU_CONSTANT,GPU_PRIMARY_COLOR);
    } else if(!((a==b||c==7)&&d==0)){
        port_log("Unsupported second alpha cycle %08x %08x\n",w0,w1);abort();
    }
}

"""N64 tile addressing and bounded texture uploads for the 3DS backend."""
def frontend(pc):
    # Upload initializes a new C3D_Tex and overwrites any earlier sampler state.
    # Mark the cache entry unknown so the first draw sets even point/wrap (0,0).
    pc=pc.replace('    gfx_rapi->set_sampler_parameters(tile, false, 0, 0);', '')
    pc=pc.replace('    (*node)->cms = 0;', '    (*node)->cms = 255;')
    pc=pc.replace('    (*node)->cmt = 0;', '    (*node)->cmt = 255;')
    pc=pc.replace('if ((*node)->texture_addr == orig_addr &&', 'if (!(native_test_dump_textures&&ssb_frame_count==850) && (*node)->texture_addr == orig_addr &&')
    pc=pc.replace('(*node)->texture_addr == orig_addr &&', 'nativeTextureAlive((*node)->texture_id) && (*node)->texture_addr == orig_addr &&')
    pc=pc.replace('    gfx_rapi->shader_get_info(prg, &num_inputs, used_textures);', '''    gfx_rapi->shader_get_info(prg, &num_inputs, used_textures);
    for(unsigned i=0;i<2;i++)if(used_textures[i]&&rendering_state.textures[i]){
        unsigned id=rendering_state.textures[i]->texture_id;
        if(!nativeTextureAlive(id))rdp.textures_changed[i]=true;
        else nativeTextureTouch(id);
    }''')
    pc=pc.replace('uint8_t cms, cmt;', 'uint8_t cms,cmt,masks,maskt,shifts,shiftt,palette_index;')
    pc=pc.replace('    } texture_tile;', '    } texture_tile;\n    uint16_t effective_width[2],effective_height[2],physical_width[2],physical_height[2];')
    pc=pc.replace('SUPPORT_CHECK(palette == 0);', 'rdp.texture_tile.palette_index=palette;\n        rdp.texture_tile.masks=masks;rdp.texture_tile.maskt=maskt;\n        rdp.texture_tile.shifts=shifts;rdp.texture_tile.shiftt=shiftt;')
    # CI4 selects one of sixteen 16-entry palette banks.
    a=pc.index('static void import_texture_ci4');b=pc.index('static void import_texture_ci8',a)
    pc=pc[:a]+pc[a:b].replace('rdp.palette[idx * 2', 'rdp.palette[(idx|rdp.texture_tile.palette_index*16) * 2')+pc[b:]
    pc=pc.replace('uint32_t bytes,line,palette_hash;', 'uint32_t bytes,line,palette_hash;\n    uint16_t width,height,source_width,source_height;\n    uint8_t upload_cms,upload_cmt;')
    pc=pc.replace('(*node)->palette==rdp.palette && (*node)->palette_hash==rdp.palette_hash',
        '(fmt!=G_IM_FMT_CI||((*node)->palette==rdp.palette&&(*node)->palette_hash==rdp.palette_hash&&(*node)->palette_index==rdp.texture_tile.palette_index))')
    pc=pc.replace('(*node)->line==rdp.texture_tile.line_size_bytes)',
        '(*node)->line==rdp.texture_tile.line_size_bytes&&(*node)->width==rdp.effective_width[tile]&&(*node)->height==rdp.effective_height[tile]&&(*node)->source_width==rdp.physical_width[tile]&&(*node)->source_height==rdp.physical_height[tile]&&(*node)->upload_cms==rdp.texture_tile.cms&&(*node)->upload_cmt==rdp.texture_tile.cmt)')
    pc=pc.replace('    (*node)->siz = siz;', '    (*node)->width=rdp.effective_width[tile];(*node)->height=rdp.effective_height[tile];\n    (*node)->source_width=rdp.physical_width[tile];(*node)->source_height=rdp.physical_height[tile];\n    (*node)->upload_cms=rdp.texture_tile.cms;(*node)->upload_cmt=rdp.texture_tile.cmt;\n    (*node)->palette_index=rdp.texture_tile.palette_index;\n    (*node)->siz = siz;')
    helper='''static void native_texture_dimensions(int tile) {
    unsigned line=rdp.texture_tile.line_size_bytes,bits=4u<<rdp.texture_tile.siz;
    SUPPORT_CHECK(line>0 && rdp.loaded_texture[tile].size_bytes>0);
    unsigned width=bits==32?line/2:line*8/bits;
    unsigned height=rdp.loaded_texture[tile].size_bytes/(line*(bits==32?2:1));
    unsigned sw=(rdp.texture_tile.lrs-rdp.texture_tile.uls)/4+1;
    unsigned sh=(rdp.texture_tile.lrt-rdp.texture_tile.ult)/4+1;
    if(rdp.texture_tile.masks){unsigned mask=1u<<rdp.texture_tile.masks;if(mask<width)width=mask;}
    if(rdp.texture_tile.maskt){unsigned mask=1u<<rdp.texture_tile.maskt;if(mask<height)height=mask;}
    if((rdp.texture_tile.cms&G_TX_CLAMP)&&sw<width)width=sw;
    if((rdp.texture_tile.cmt&G_TX_CLAMP)&&sh<height)height=sh;
    SUPPORT_CHECK(width>0&&height>0&&width*height<=8192);
    rdp.physical_width[tile]=width;rdp.physical_height[tile]=height;
    rdp.effective_width[tile]=(rdp.texture_tile.cms&G_TX_CLAMP)?sw:width;
    rdp.effective_height[tile]=(rdp.texture_tile.cmt&G_TX_CLAMP)?sh:height;
    SUPPORT_CHECK(rdp.effective_width[tile]<=1024&&rdp.effective_height[tile]<=1024);
}
static void native_texture_upload(const uint8_t* pixels,unsigned width,unsigned height,int tile){
    static uint8_t cropped[32768] __attribute__((aligned(32)));
    unsigned w=rdp.physical_width[tile],h=rdp.physical_height[tile];
    SUPPORT_CHECK(w<=width&&h<=height);
    if(w!=width){
        for(unsigned y=0;y<h;y++)memcpy(cropped+y*w*4,pixels+y*width*4,w*4);
        pixels=cropped;
    }
    native_texture_clamp_s=(rdp.texture_tile.cms&G_TX_CLAMP)!=0;
    native_texture_clamp_t=(rdp.texture_tile.cmt&G_TX_CLAMP)!=0;
    extern int native_texture_16bit;
    native_texture_16bit=rdp.texture_tile.fmt==G_IM_FMT_CI||
        (rdp.texture_tile.fmt==G_IM_FMT_RGBA&&rdp.texture_tile.siz==G_IM_SIZ_16b);
    extern unsigned native_texture_width,native_texture_height,native_texture_mirror;
    native_texture_width=rdp.effective_width[tile];native_texture_height=rdp.effective_height[tile];
    native_texture_mirror=(rdp.texture_tile.cms&G_TX_MIRROR)|((rdp.texture_tile.cmt&G_TX_MIRROR)<<1);
    nativeDumpTexture(pixels,w,h,rdp.loaded_texture[tile].addr,rdp.texture_tile.fmt,rdp.texture_tile.siz,
        rdp.texture_tile.line_size_bytes,rdp.texture_tile.masks|(rdp.texture_tile.maskt<<8),rdp.texture_tile.shifts|(rdp.texture_tile.shiftt<<8));
    gfx_rapi->upload_texture(pixels,w,h);
}
'''
    start=pc.index('static void import_texture_rgba16');end=pc.index('static void import_texture(int tile)',start)
    block=pc[start:end].replace('gfx_rapi->upload_texture(rgba32_buf, width, height);','native_texture_upload(rgba32_buf,width,height,tile);')
    block=block.replace('gfx_rapi->upload_texture(rdp.loaded_texture[tile].pixels, width, height);','native_texture_upload(rdp.loaded_texture[tile].pixels,width,height,tile);')
    pc=pc[:start]+helper+block+pc[end:]
    pc=pc.replace('static void import_texture(int tile) {','static void import_texture(int tile) {\n    native_texture_dimensions(tile);')
    pc=pc.replace('uint32_t tex_width = (rdp.texture_tile.lrs - rdp.texture_tile.uls + 4)  >> 2;', 'uint32_t tex_width = rdp.effective_width[0];')
    pc=pc.replace('uint32_t tex_height = (rdp.texture_tile.lrt - rdp.texture_tile.ult + 4) >> 2;', 'uint32_t tex_height = rdp.effective_height[0];')
    pc=pc.replace('float u = (v_arr[i]->u - rdp.texture_tile.uls * 8) / 32.0f;',
        'unsigned ss=rdp.texture_tile.shifts;float su=ss>10?(float)(1u<<(16-ss)):1.0f/(1u<<ss);\n            float u=v_arr[i]->u*(su/32.0f)-rdp.texture_tile.uls/4.0f;')
    pc=pc.replace('float v = (v_arr[i]->v - rdp.texture_tile.ult * 8) / 32.0f;',
        'unsigned st=rdp.texture_tile.shiftt;float sv=st>10?(float)(1u<<(16-st)):1.0f/(1u<<st);\n            float v=v_arr[i]->v*(sv/32.0f)-rdp.texture_tile.ult/4.0f;')
    return pc

def backend(code):
    from prepare_render import function
    code=code.replace('static u32 sTextureIndex;', 'static u32 sTextureIndex;\nint native_texture_clamp_s,native_texture_clamp_t,native_texture_16bit;\nunsigned native_texture_width,native_texture_height,native_texture_mirror;')
    code=code.replace('static int sTexUnits[2];', '''static int sTexUnits[2];
extern volatile uint32_t ssb_frame_count;
static uint32_t nativeTextureLastUse[TEXTURE_POOL_SIZE];
int nativeTextureAlive(unsigned id){return id<TEXTURE_POOL_SIZE&&sTexturePool[id].data!=NULL;}
void nativeTextureTouch(unsigned id){if(id<TEXTURE_POOL_SIZE)nativeTextureLastUse[id]=ssb_frame_count;}
/* FrameBegin waited for the previous submission. Only this frame's queued
 * textures must remain pinned; earlier frames can be reclaimed immediately. */
static unsigned nativeTextureEvictOne(void){
    int oldest=-1;
    for(unsigned i=0;i<sTextureIndex;i++){
        if(!sTexturePool[i].data||nativeTextureLastUse[i]==ssb_frame_count)continue;
        if(oldest<0||nativeTextureLastUse[i]<nativeTextureLastUse[oldest])oldest=i;
    }
    if(oldest<0)return 0;
    unsigned bytes=sTexturePool[oldest].size;
    C3D_TexDelete(&sTexturePool[oldest]);
    memset(&sTexturePool[oldest],0,sizeof(C3D_Tex));
    return bytes;
}
static void nativeTextureMakeRoom(unsigned bytes){
    unsigned freed=0;
    while(linearSpaceFree()<bytes+4*1024*1024){
        unsigned n=nativeTextureEvictOne();if(!n)break;freed+=n;
    }
    if(freed)port_log("Texture reclaim frame=%u bytes=%u free=%u\\n",ssb_frame_count,freed,linearSpaceFree());
}''')
    code=code.replace('    C3D_TexBind(tile, &sTexturePool[texture_id]);', '    nativeTextureLastUse[texture_id]=ssb_frame_count;\n    C3D_TexBind(tile, &sTexturePool[texture_id]);')
    code=function(code,'gfx_citro3d_upload_texture','''    unsigned logicalW=native_texture_width,logicalH=native_texture_height;
    unsigned w=logicalW<8?8:1u<<(32-__builtin_clz(logicalW-1));
    unsigned h=logicalH<8?8:1u<<(32-__builtin_clz(logicalH-1));
    if(w>1024||h>1024){port_log("Texture dimensions unsupported %ux%u logical=%ux%u source=%dx%d\\n",w,h,logicalW,logicalH,width,height);abort();}
    if(sTexturePool[sCurTex].data)nativeRetireTexture(&sTexturePool[sCurTex]);
    memset(&sTexturePool[sCurTex],0,sizeof(C3D_Tex));
    unsigned pixelBytes=native_texture_16bit?2:4;
    native_perf_render.upload_bytes+=w*h*pixelBytes;
    nativeTextureMakeRoom(w*h*pixelBytes);
    while(!C3D_TexInit(&sTexturePool[sCurTex],w,h,native_texture_16bit?GPU_RGBA5551:GPU_RGBA8)){
        if(nativeTextureEvictOne())continue;
        port_log("Texture allocation failed %ux%u logical=%ux%u source=%dx%d free=%u slot=%u\\n",w,h,logicalW,logicalH,width,height,linearSpaceFree(),sCurTex);abort();
    }
    u8* dst=sTexturePool[sCurTex].data;
    static u16 sourceX[1024],sourceY[1024];
    /* Resolve wrapping once per row/column instead of dividing per texel. */
    for(unsigned x=0;x<w;x++){
        unsigned s=native_texture_clamp_s&&x>=logicalW?logicalW-1:x;
        bool mirror=native_texture_clamp_s&&(native_texture_mirror&1)&&((s/width)&1);
        s%=width;sourceX[x]=mirror?width-1-s:s;
    }
    for(unsigned y=0;y<h;y++){
        unsigned t=native_texture_clamp_t&&y>=logicalH?logicalH-1:y;
        bool mirror=native_texture_clamp_t&&(native_texture_mirror&2)&&((t/height)&1);
        t%=height;sourceY[y]=mirror?height-1-t:t;
    }
    /* Bake mask/mirror inside a larger clamp rectangle once per cached upload.
     * PICA samples the result directly, with no extra passes or fragment work. */
    for(unsigned by=0;by<h;by+=8)for(unsigned bx=0;bx<w;bx+=8){
        for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++){
            unsigned sx=sourceX[bx+x],sy=sourceY[by+y];
            u32 c=((const u32*)rgba32_buf)[sy*width+sx];
            unsigned pos=sTileOrder[(x&3)+((y&3)<<2)]+((x>>2)<<4)+((y>>2)<<5);
            /* CI palettes and RGBA16 contain exactly 5/5/5/1 bits. Restoring
             * that original format halves GPU storage without losing color. */
            if(native_texture_16bit)((u16*)dst)[pos]=((c>>3)&31)<<11|((c>>11)&31)<<6|((c>>19)&31)<<1|(c>>31);
            else ((u32*)dst)[pos]=__builtin_bswap32(c);
        }
        dst+=64*pixelBytes;
    }
    sTexturePoolScaleS[sCurTex]=(float)logicalW/w;
    sTexturePoolScaleT[sCurTex]=(float)logicalH/h;
    C3D_TexFlush(&sTexturePool[sCurTex]);''')
    return code

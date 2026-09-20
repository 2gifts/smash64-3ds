"""Keep all eight tile descriptors and emulate texture-memory loads natively."""
import re
def frontend(pc,replace_function):
    pattern=r'    struct \{\n        uint8_t fmt;\n        uint8_t siz;.*?    \} texture_tile;'
    match=re.search(pattern,pc,re.S);assert match
    definition=match[0].replace('    struct {','struct NativeTile {',1).replace('    } texture_tile;','};')
    pc=pc[:match.start()]+'    struct NativeTile texture_tile,tiles[8],render_tiles[2];\n    unsigned first_tile;\n    uint8_t tmem[4096];\n    const uint8_t* tmem_origin[512];\n    uint32_t texture_hash[2];'+pc[match.end():]
    pc=pc.replace('static struct RDP {',definition+'\n\nstatic struct RDP {')
    pc=pc.replace('uint32_t bytes,line,palette_hash;', 'uint32_t bytes,line,palette_hash,content_hash;')
    pc=pc.replace('(*node)->line==rdp.texture_tile.line_size_bytes', '(*node)->content_hash==rdp.texture_hash[tile]&&(*node)->line==rdp.texture_tile.line_size_bytes')
    pc=pc.replace('    (*node)->siz = siz;', '    (*node)->content_hash=rdp.texture_hash[tile];\n    (*node)->siz = siz;')
    pc=pc.replace('uint8_t tmem[4096];','uint8_t tmem[4096] __attribute__((aligned(4)));')
    pc=pc.replace('uint8_t palette_data[512];','uint8_t palette_data[512] __attribute__((aligned(4)));')
    helper='''#include "native_texture_hash.h"
static void nativeTmemWrite(unsigned offset,const uint8_t* data,unsigned size){
    SUPPORT_CHECK(offset<4096&&size<=4096-offset);
    memcpy(rdp.tmem+offset,data,size);
    for(unsigned i=0;i<size;i+=8)rdp.tmem_origin[(offset+i)/8]=data+i;
    rdp.textures_changed[0]=rdp.textures_changed[1]=true;
}
static void nativePrepareTile(int unit){
    unsigned start=rdp.tile_tmem[(rdp.first_tile+unit)&7]*8;
    unsigned bits=4u<<rdp.texture_tile.siz;
    unsigned pitch=rdp.texture_tile.line_size_bytes*(bits==32?2:1);
    unsigned height=(rdp.texture_tile.lrt-rdp.texture_tile.ult)/4+1;
    if(rdp.texture_tile.maskt){unsigned period=1u<<rdp.texture_tile.maskt;if(period<height||!(rdp.texture_tile.cmt&G_TX_CLAMP))height=period;}
    SUPPORT_CHECK(start<4096&&pitch>0&&pitch<=4096-start);
    unsigned bytes=pitch*height;if(bytes>4096-start)bytes=(4096-start)/pitch*pitch;
    rdp.loaded_texture[unit].pixels=rdp.tmem+start;
    rdp.loaded_texture[unit].addr=rdp.tmem_origin[start/8]?rdp.tmem_origin[start/8]:rdp.tmem+start;
    rdp.loaded_texture[unit].size_bytes=bytes;
    rdp.texture_hash[unit]=nativeTextureHash(rdp.tmem+start,bytes);
}
'''
    pc=pc.replace('static void native_texture_dimensions',helper+'\nstatic void native_texture_dimensions')
    pc=pc.replace('    memcpy(rdp.palette_data+offset,rdp.texture_to_load.addr,bytes);', '    if(rdp.palette&&!memcmp(rdp.palette_data+offset,rdp.texture_to_load.addr,bytes))return;\n    memcpy(rdp.palette_data+offset,rdp.texture_to_load.addr,bytes);')
    pc=pc.replace('    uint32_t hash=2166136261u;\n    for(unsigned i=0;i<512;i++)hash=(hash^rdp.palette_data[i])*16777619u;\n    rdp.palette_hash=hash;', '    rdp.palette_hash=nativeTextureHash(rdp.palette_data,512);')
    pc=replace_function(pc,'gfx_dp_load_block','''    SUPPORT_CHECK(tile<8&&uls==0&&ult==0);
    unsigned bytes=((lrs+1)*(4u<<rdp.texture_to_load.siz)+7)/8;
    nativeFixTexture(rdp.texture_to_load.addr,bytes);
    nativeTmemWrite(rdp.tile_tmem[tile]*8,rdp.texture_to_load.addr,bytes);''')
    pc=replace_function(pc,'gfx_dp_load_tile','''    SUPPORT_CHECK(tile<8&&lrs>=uls&&lrt>=ult);
    unsigned bits=4u<<rdp.texture_to_load.siz,x=uls>>2,y=ult>>2;
    unsigned w=((lrs-uls)>>2)+1,h=((lrt-ult)>>2)+1;
    unsigned stride=(rdp.texture_to_load.width*bits+7)/8,rowbytes=(w*bits+7)/8;
    unsigned pitch=rdp.tile_line[tile]?(rdp.tile_line[tile]*(bits==32?2:1)):rowbytes;
    unsigned offset=y*stride+x*bits/8,target=rdp.tile_tmem[tile]*8;
    SUPPORT_CHECK(pitch>=rowbytes&&target+pitch*h<=4096&&!((x*bits)&7));
    nativeFixTexture(rdp.texture_to_load.addr,offset+(h-1)*stride+rowbytes);
    for(unsigned row=0;row<h;row++)nativeTmemWrite(target+row*pitch,rdp.texture_to_load.addr+offset+row*stride,rowbytes);''')
    pc=replace_function(pc,'gfx_dp_set_tile','''    SUPPORT_CHECK(tile<8);
    struct NativeTile* t=&rdp.tiles[tile];
    if(!masks)cms=G_TX_CLAMP;if(!maskt)cmt=G_TX_CLAMP;
    t->fmt=fmt;t->siz=siz;t->cms=cms;t->cmt=cmt;t->masks=masks;t->maskt=maskt;
    t->shifts=shifts;t->shiftt=shiftt;t->palette_index=palette;t->line_size_bytes=line*8;
    rdp.tile_tmem[tile]=tmem;rdp.tile_line[tile]=line*8;
    if(tile==rdp.first_tile)rdp.texture_tile=*t;
    rdp.textures_changed[0]=rdp.textures_changed[1]=true;''')
    pc=replace_function(pc,'gfx_dp_set_tile_size','''    SUPPORT_CHECK(tile<8);
    struct NativeTile* t=&rdp.tiles[tile];
    t->uls=uls;t->ult=ult;t->lrs=lrs;t->lrt=lrt;
    if(tile==rdp.first_tile)rdp.texture_tile=*t;
    rdp.textures_changed[0]=rdp.textures_changed[1]=true;''')
    pc=pc.replace('    rsp.texture_scaling_factor.s = sc;', '    rdp.first_tile=tile;rdp.texture_tile=rdp.tiles[tile];\n    rdp.textures_changed[0]=rdp.textures_changed[1]=true;\n    rsp.texture_scaling_factor.s = sc;')
    pc=pc.replace('static void import_texture(int tile) {', '''static void import_texture_inner(int tile) {
    nativePrepareTile(tile);
    if(rdp.texture_tile.fmt==G_IM_FMT_CI)rdp.palette_hash=rdp.texture_tile.siz==G_IM_SIZ_4b?
        nativeTextureHash(rdp.palette_data+rdp.texture_tile.palette_index*32,32):nativeTextureHash(rdp.palette_data,512);''')
    end=pc.index('static void gfx_normalize_vector')
    pc=pc[:end]+'''static void import_texture(int tile){
    struct NativeTile saved=rdp.texture_tile;
    rdp.texture_tile=rdp.render_tiles[tile];
    import_texture_inner(tile);rdp.texture_tile=saved;
}
'''+pc[end:]
    pc=pc.replace('static bool gfx_texture_cache_lookup(', 'static unsigned nativeTextureHits,nativeTextureMisses;\nstatic bool gfx_texture_cache_lookup(')
    start=pc.index('static bool gfx_texture_cache_lookup');end=pc.index('#include "native_texture_hash.h"',start)
    block=pc[start:end].replace('            return true;', '            nativeTextureHits++;return true;').replace('    return false;', '    nativeTextureMisses++;return false;')
    pc=pc[:start]+block+pc[end:]
    pc=pc.replace('void gfx_start_frame(void) {', 'void gfx_start_frame(void) {\n    nativeTextureHits=nativeTextureMisses=0;')
    pc=pc.replace('void gfx_end_frame(void) {', 'void gfx_end_frame(void) {\n    native_perf_render.texture_hits=nativeTextureHits;native_perf_render.texture_misses=nativeTextureMisses;\n    extern volatile uint32_t ssb_frame_count;\n    if(ssb_frame_count%180==0)port_log("TEXTURE_CACHE frame=%u hits=%u misses=%u pool=%u\\n",ssb_frame_count,nativeTextureHits,nativeTextureMisses,gfx_texture_cache.pool_pos);')
    a=pc.index('    for (int i = 0; i < 2; i++) {',pc.index('gfx_rapi->shader_get_info'))
    b=pc.index('    bool use_texture',a)
    block=pc[a:b].replace('        if (used_textures[i]) {','        if (used_textures[i]) {\n            struct NativeTile* tileState=&rdp.render_tiles[i];')
    block=block.replace('rdp.texture_tile.cms','tileState->cms').replace('rdp.texture_tile.cmt','tileState->cmt')
    pc=pc[:a]+block+pc[b:]
    pc=pc.replace('    gfx_rapi->shader_get_info(prg, &num_inputs, used_textures);', '''    gfx_rapi->shader_get_info(prg, &num_inputs, used_textures);
    for(unsigned unit=0;unit<2;unit++)if(used_textures[unit]){
        struct NativeTile t=rdp.tiles[(rdp.first_tile+unit)&7];
        /* A masked texture can use PICA wrapping directly when the entire
         * triangle stays within its clamp bounds. The edge cases retain the
         * baked clamp image. This avoids duplicating huge repeated interiors. */
        for(unsigned axis=0;axis<2;axis++){
            unsigned mode=axis?t.cmt:t.cms,mask=axis?t.maskt:t.masks;
            unsigned shift=axis?t.shiftt:t.shifts;
            float lo=(axis?t.ult:t.uls)/4.0f;
            float hi=(axis?t.lrt:t.lrs)/4.0f-lo;
            if(!(mode&G_TX_CLAMP)||!mask||hi+1<=(1u<<mask))continue;
            float scale=shift>10?(float)(1u<<(16-shift))/32.0f:1.0f/(32u<<shift);
            bool inside=true;
            for(unsigned n=0;n<3;n++){
                float uv=(axis?v_arr[n]->v:v_arr[n]->u)*scale-lo;
                if(uv<0.0f||uv>hi||v_arr[n]->w<=0.0f){inside=false;break;}
            }
            if(inside){if(axis)t.cmt&=~G_TX_CLAMP;else t.cms&=~G_TX_CLAMP;}
        }
        if(t.cms!=rdp.render_tiles[unit].cms||t.cmt!=rdp.render_tiles[unit].cmt)rdp.textures_changed[unit]=true;
        rdp.render_tiles[unit]=t;
    }''')
    a=pc.index('        if (use_texture) {',pc.index('    bool use_texture'));b=pc.index('#ifndef TARGET_N3DS',a)
    pc=pc[:a]+'''        if(use_texture)for(unsigned unit=0;unit<2;unit++){
            struct NativeTile* tile=&rdp.tiles[(rdp.first_tile+unit)&7];
            unsigned ss=tile->shifts,st=tile->shiftt;
            float su=ss>10?(float)(1u<<(16-ss)):1.0f/(1u<<ss);
            float sv=st>10?(float)(1u<<(16-st)):1.0f/(1u<<st);
            float u=v_arr[i]->u*(su/32.0f)-tile->uls/4.0f;
            float v=v_arr[i]->v*(sv/32.0f)-tile->ult/4.0f;
            static unsigned uvTrace;
            if(ssb_frame_count==850&&i==0&&unit==0&&uvTrace++<170)port_log("UV tex=%p st=%.1f,%.1f size=%u,%u tile=%u,%u,%u,%u wrap=%u,%u shift=%u,%u uv=%.3f,%.3f\\n",rdp.loaded_texture[unit].addr,v_arr[i]->u,v_arr[i]->v,rdp.effective_width[unit],rdp.effective_height[unit],tile->uls,tile->ult,tile->lrs,tile->lrt,tile->cms,tile->cmt,ss,st,u,v);
            if((rdp.other_mode_h&(3u<<G_MDSFT_TEXTFILT))!=G_TF_POINT){u+=0.5f;v+=0.5f;}
            buf_vbo[buf_vbo_len++]=used_textures[unit]?u/rdp.effective_width[unit]:0;
            buf_vbo[buf_vbo_len++]=used_textures[unit]?v/rdp.effective_height[unit]:0;
        }
'''+pc[b:]
    a=pc.index('static void gfx_dp_texture_rectangle');b=pc.index('static void gfx_dp_fill_rectangle',a)
    block=pc[a:b].replace('    uint32_t saved_combine_mode', '    unsigned saved_tile=rdp.first_tile;\n    rdp.first_tile=tile;rdp.texture_tile=rdp.tiles[tile];\n    rdp.textures_changed[0]=rdp.textures_changed[1]=true;\n    uint32_t saved_combine_mode',1)
    block=block.replace('    rdp.combine_mode = saved_combine_mode;', '    rdp.combine_mode = saved_combine_mode;\n    rdp.first_tile=saved_tile;rdp.texture_tile=rdp.tiles[saved_tile];\n    rdp.textures_changed[0]=rdp.textures_changed[1]=true;')
    return pc[:a]+block+pc[b:]

def backend(code):
    code=code.replace('prg->num_floats += 2;', 'prg->num_floats += 4;')
    code=code.replace('vtxOffs += 2;', 'vtxOffs += 4;')
    original='''            *dst++ = buf_vbo[offset + vtxOffs++] * sTexturePoolScaleS[sCurTex];
            *dst++ = 1 - (buf_vbo[offset + vtxOffs++] * sTexturePoolScaleT[sCurTex]);'''
    replacement='''            for(unsigned unit=0;unit<2;unit++){
                *dst++=buf_vbo[offset+vtxOffs++]*sTexturePoolScaleS[sTexUnits[unit]];
                *dst++=1-buf_vbo[offset+vtxOffs++]*sTexturePoolScaleT[sTexUnits[unit]];
            }'''
    assert code.count(original)==2
    code=code.replace(original,replacement)
    code=code.replace('''            *dst++ = 0;
            *dst++ = 0;''','''            *dst++=0;*dst++=0;*dst++=0;*dst++=0;''')
    code=code.replace('AttrInfo_AddLoader(attrInfo, 1, GPU_FLOAT, 2);','AttrInfo_AddLoader(attrInfo, 1, GPU_FLOAT, 4);')
    return code

"""Adapt the inspected sm64-port 3DS backend; retain upstream sources alongside it."""
import re
import shutil
from build import ROOT,RENDER_SOURCE
import prepare_texture
import prepare_tmem
import prepare_ui

SOURCE=RENDER_SOURCE/'src/pc/gfx'
OUT=ROOT/'renderer'
def function(text,name,body):
    pattern=r'((?:static )?(?:inline )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{).*?^}'
    result,count=re.subn(pattern,lambda m:m[1]+'\n'+body+'\n}',text,flags=re.M|re.S)
    if count!=1:raise ValueError((name,count))
    return result
def main():
    OUT.mkdir(exist_ok=True)
    for name in ['gfx_pc.h','gfx_cc.h','gfx_cc.c','gfx_window_manager_api.h','gfx_rendering_api.h','gfx_screen_config.h','shader.v.pica']:
        shutil.copy2(SOURCE/name,OUT/name)
    pc=(SOURCE/'gfx_pc.c').read_text()
    # Credits use a 640x480 logical canvas; rasterize it into the same 320x240
    # physical viewport without allocating an oversized render target.
    pc=pc.replace('#define SCREEN_WIDTH 320', 'extern uint32_t native_game_width,native_game_height;\n#define SCREEN_WIDTH native_game_width')
    pc=pc.replace('#define SCREEN_HEIGHT 240', '#define SCREEN_HEIGHT native_game_height')
    pc=pc.replace('#include "gfx_3ds.h"','#include "rsp_platform.h"').replace('#include "src/pc/profiler_3ds.h"','#define profiler_3ds_log_time(id) ((void)0)')
    pc=pc.replace('#define SUPPORT_CHECK(x) assert(x)', '#undef assert\n#define assert(x) ((x)?(void)0:nativeRenderAssertion(#x,__LINE__,native_current_dl))\n#define SUPPORT_CHECK(x) assert(x)')
    pc=pc.replace('#define MAX_LIGHTS 2','#define MAX_LIGHTS 7')
    pc=pc.replace('float wMod = w * 1.2f; // expanded w-range for testing clip rejection', 'float wMod=w+(native_stereo_perspective?fabsf(gSliderLevel*NATIVE_STEREO_SHIFT_MAX*(w-native_stereo_focus_w)):0.0f);')
    pc=pc.replace('if (y < -wMod)', 'if (y < -w)').replace('if (y > wMod)', 'if (y > w)')
    # N64 intensity textures replicate intensity into alpha as well as RGB.
    a=pc.index('static void import_texture_i4');b=pc.index('static void import_texture_ci4',a)
    block=pc[a:b].replace('rgba32_buf[4*i + 3] = 255;', 'rgba32_buf[4*i + 3] = rgba32_buf[4*i + 0];')
    pc=pc[:a]+block+pc[b:]
    for name in ['env','prim']:
        needle='static void gfx_dp_set_'+name+'_color(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {'
        pc=pc.replace(needle,needle+'\n    if(rdp.'+name+'_color.r!=r||rdp.'+name+'_color.g!=g||rdp.'+name+'_color.b!=b||rdp.'+name+'_color.a!=a)gfx_flush();')
    # Preserve the RDP ONE operand. SM64's original compact combiner omitted it.
    pc=pc.replace('uint32_t cc_id','uint64_t cc_id')
    pc=pc.replace('(cc_id >> 24) << 24','(uint32_t)(cc_id >> 32) << 24')
    pc=pc.replace('(cc_id >> (i * 3)) & 7','(cc_id >> (i * 4)) & 15')
    pc=pc.replace('(cc_id >> (12 + i * 3)) & 7','(cc_id >> (16 + i * 4)) & 15')
    pc=pc.replace('uint8_t input_number[8]', 'uint8_t input_number[16]')
    pc=pc.replace('                case CC_LOD:\n', '                case CC_ONE:\n                case CC_LOD:\n',1)
    pc=pc.replace('cc_id &= ~0xfff000;', 'cc_id &= ~0xffff0000ull;')
    pc=pc.replace('cc_id |= SHADER_OPT_', 'cc_id |= (uint64_t)SHADER_OPT_')
    for flag in ['ALPHA','FOG','TEXTURE_EDGE','NOISE']:
        pc=pc.replace('cc_id |= (uint64_t)SHADER_OPT_'+flag+';', 'cc_id |= (uint64_t)SHADER_OPT_'+flag+' << 8;')
    pc=pc.replace('        case G_CCMUX_LOD_FRACTION:', '        case G_CCMUX_1:\n            return CC_ONE;\n        case G_CCMUX_LOD_FRACTION:')
    pc=pc.replace('(color_comb_component(b) << 3)', '(color_comb_component(b) << 4)').replace('(color_comb_component(c) << 6)', '(color_comb_component(c) << 8)').replace('(color_comb_component(d) << 9)', '(color_comb_component(d) << 12)')
    pc=pc.replace('rgb | (alpha << 12)', 'rgb | (alpha << 16)')
    pc=pc.replace('                    case CC_LOD:\n', '                    case CC_ONE:\n                        tmp=(struct RGBA){255,255,255,255};color=&tmp;break;\n                    case CC_LOD:\n')
    # Match BattleShip/libultraship's widening and CPU particle/indicator hooks.
    # Authored RDP rectangles fill the canvas; projected geometry gains FOV.
    pc=function(pc,'gfx_adjust_x_for_aspect_ratio','    return x*nativeDisplayClipScale();')
    pc=pc.replace('    ulxf = gfx_adjust_x_for_aspect_ratio(ulxf);','')
    pc=pc.replace('    lrxf = gfx_adjust_x_for_aspect_ratio(lrxf);','')
    pc=pc.replace('color_combiner_pool[64]','color_combiner_pool[512]').replace('uint8_t color_combiner_pool_size','uint16_t color_combiner_pool_size')
    pc=pc.replace('struct ColorCombiner *comb = &color_combiner_pool[color_combiner_pool_size++];','SUPPORT_CHECK(color_combiner_pool_size < 512);\n    struct ColorCombiner *comb = &color_combiner_pool[color_combiner_pool_size++];')
    pc=pc.replace('uint32_t other_mode_l, other_mode_h;', 'uint32_t other_mode_l, other_mode_h;\n    uint32_t blend_color,prim_depth,combine_raw[2];')
    pc=pc.replace('            case G_SETCOMBINE:', '            case G_SETCOMBINE:\n                rdp.combine_raw[0]=cmd->words.w0;rdp.combine_raw[1]=cmd->words.w1;')
    pc=pc.replace('    uint64_t cc_id = rdp.combine_mode;', '    nativeCombineTrace(rdp.combine_raw[0],rdp.combine_raw[1],rdp.other_mode_l,rdp.other_mode_h);\n    uint64_t cc_id = rdp.combine_mode;')
    pc=pc.replace('bool use_fog = (rdp.other_mode_l >> 30) == G_BL_CLR_FOG;', '''bool fog_blend=(rdp.other_mode_l>>30)==G_BL_CLR_FOG;
    bool use_fog=fog_blend&&((rdp.other_mode_l>>26)&3)==G_BL_A_SHADE;
    native_fog_primitive=fog_blend&&((rdp.other_mode_l>>26)&3)==G_BL_A_FOG;''')
    pc=pc.replace('static void gfx_sp_set_other_mode(uint32_t shift, uint32_t num_bits, uint64_t mode) {', 'static void gfx_sp_set_other_mode(uint32_t shift, uint32_t num_bits, uint64_t mode) {\n    gfx_flush();')
    pc=pc.replace('static void gfx_dp_set_fog_color(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {', 'static void gfx_dp_set_fog_color(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {\n    gfx_flush();')
    pc=pc.replace('        uint8_t tile_number;', '        uint8_t tile_number;\n        uint16_t width;')
    pc=pc.replace('        uint32_t size_bytes;', '        uint32_t size_bytes;\n        const uint8_t* pixels;\n        uint8_t staging[4096];')
    pc=pc.replace('    const uint8_t *palette;', '    const uint8_t *palette;\n    uint8_t palette_data[512];\n    uint32_t palette_hash;\n    uint16_t tile_tmem[8],tile_line[8];')
    pc=pc.replace('    rdp.texture_to_load.siz = size;', '    rdp.texture_to_load.siz = size;\n    rdp.texture_to_load.width = width+1;')
    pc=pc.replace('    if (tile == G_TX_RENDERTILE) {\n        SUPPORT_CHECK(palette == 0);', '    rdp.tile_tmem[tile]=tmem;rdp.tile_line[tile]=line*8;\n    if (tile == G_TX_RENDERTILE) {\n        SUPPORT_CHECK(palette == 0);')
    pc=pc.replace('    for (size_t i = 0; i < n_vertices; i++, dest_index++) {','    SUPPORT_CHECK(dest_index+n_vertices <= MAX_VERTICES);\n    portRelocFixupVertexAtRuntime(vertices,n_vertices);\n    for (size_t i = 0; i < n_vertices; i++, dest_index++) {')
    pc=pc.replace('static inline void *seg_addr(uintptr_t w1) {\n    return (void *) w1;\n}', 'static inline void *seg_addr(uintptr_t w1) {\n    return nativeResolveGfxAddress(w1, native_current_dl, false);\n}')
    pc=pc.replace('static void gfx_run_dl(Gfx* cmd) {\n    for (;;) {','static void gfx_run_dl(Gfx* cmd) {\n    native_dl_enter();\n    for (;;) {\n        native_current_dl=cmd;\n        native_dl_check(cmd);')
    pc=pc.replace('case (uint8_t)G_ENDDL:\n                return;', 'case (uint8_t)G_ENDDL:\n                native_dl_leave();\n                return;')
    pc=pc.replace('(Gfx *)seg_addr(cmd->words.w1)', '(Gfx *)nativeResolveGfxAddress(cmd->words.w1,cmd,true)')
    pc=pc.replace('        case G_MW_NUMLIGHT:', '        case G_MW_SEGMENT:\n            nativeSetSegment(offset/4,data);\n            break;\n        case G_MW_NUMLIGHT:')
    pc=pc.replace('        case G_MW_SEGMENT:', '''        case G_MW_MATRIX: {
            SUPPORT_CHECK(offset<64 && !(offset&3));
            unsigned element=(offset&31)/2;
            float* matrix=&rsp.MP_matrix[0][0];
            for(unsigned i=0;i<2;i++) {
                uint16_t part=(uint16_t)(data>>(16-i*16));
                float previous=matrix[element+i];
                matrix[element+i]=(offset&32)?floorf(previous)+part/65536.0f:
                    (float)(int16_t)part+(previous-floorf(previous));
            }
            break;
        }
        case G_MW_SEGMENT:''')
    pc=pc.replace('        case G_MW_FOG:', '''        case G_MW_LIGHTCOL: {
            unsigned light=offset/24,part=offset%24;
            SUPPORT_CHECK(light<=MAX_LIGHTS && (part==0||part==4));
            unsigned char* color=(part==0)?rsp.current_lights[light].col:rsp.current_lights[light].colc;
            color[0]=data>>24;color[1]=data>>16;color[2]=data>>8;
            break;
        }
        case G_MW_FOG:''')
    pc=pc.replace('    rsp.lights_changed = 1;\n            break;', '    SUPPORT_CHECK(rsp.current_num_lights>=1 && rsp.current_num_lights<=MAX_LIGHTS+1);\n            rsp.lights_changed = 1;\n            break;')
    pc=pc.replace('uint8_t offset, const void* data)', 'uint8_t offset, const void* data, unsigned size)')
    pc=pc.replace('C0(8, 8) * 8, seg_addr(cmd->words.w1))', 'C0(8, 8) * 8, seg_addr(cmd->words.w1), (C0(19,5)+1)*8)')
    pc=pc.replace('memcpy(rsp.current_lights + lightidx, data, sizeof(Light_t));', 'memset(rsp.current_lights+lightidx,0,sizeof(Light_t));\n                memcpy(rsp.current_lights+lightidx,data,size<sizeof(Light_t)?size:sizeof(Light_t));\n                rsp.lights_changed=1;')
    # F3DEX2 reserves the first two light slots for environment-map LookAt axes.
    pc=pc.replace('    float current_lookat_coeffs[2][3];', '    Light_t current_lookat[2];\n    unsigned lookat_valid;\n    float current_lookat_coeffs[2][3];')
    pc=pc.replace('            int lightidx = offset / 24 - 2;', '''            int lightidx = offset / 24 - 2;
            if(lightidx==-2 || lightidx==-1){
                unsigned axis=lightidx+2;
                memset(&rsp.current_lookat[axis],0,sizeof(Light_t));
                memcpy(&rsp.current_lookat[axis],data,size<sizeof(Light_t)?size:sizeof(Light_t));
                rsp.lookat_valid|=1u<<axis;rsp.lights_changed=true;
            }''')
    pc=pc.replace('calculate_normal_dir(&lookat_x,', 'calculate_normal_dir((rsp.lookat_valid&1)?&rsp.current_lookat[0]:&lookat_x,')
    pc=pc.replace('calculate_normal_dir(&lookat_y,', 'calculate_normal_dir((rsp.lookat_valid&2)?&rsp.current_lookat[1]:&lookat_y,')
    pc=pc.replace('static void gfx_sp_pop_matrix(uint32_t count) {', 'static void gfx_sp_pop_matrix(uint32_t count) {\n    rsp.lights_changed=true;')
    pc=pc.replace('    //if (rand()%2) return;', '''    extern volatile uint32_t ssb_frame_count;
    static unsigned shadeTrace;
    if(ssb_frame_count==850 && (rsp.geometry_mode&G_LIGHTING) && shadeTrace++<160)port_log("SHADE gm=%08x combine=%08x,%08x color=%u,%u,%u,%u lights=%u ambient=%u,%u,%u\\n",
        rsp.geometry_mode,rdp.combine_raw[0],rdp.combine_raw[1],v1->color.r,v1->color.g,v1->color.b,v1->color.a,
        rsp.current_num_lights,rsp.current_lights[rsp.current_num_lights-1].col[0],rsp.current_lights[rsp.current_num_lights-1].col[1],rsp.current_lights[rsp.current_num_lights-1].col[2]);''')
    pc=pc.replace('    if (tile == 1) return;','    if (tile == 1) return;') # second texture support is audited separately
    pc=pc.replace('    rdp.palette = rdp.texture_to_load.addr;', '    portRelocFixupTextureAtRuntime(rdp.texture_to_load.addr,(high_index+1)*2);\n    rdp.palette = rdp.texture_to_load.addr;')
    pc=pc.replace('    SUPPORT_CHECK(tile == G_TX_LOADTILE);\n    SUPPORT_CHECK(rdp.texture_to_load.siz == G_IM_SIZ_16b);','    SUPPORT_CHECK(tile < 8);\n    SUPPORT_CHECK(rdp.texture_to_load.siz == G_IM_SIZ_16b);')
    pc=pc.replace('    rdp.loaded_texture[rdp.texture_to_load.tile_number].addr = rdp.texture_to_load.addr;', '    portRelocFixupTextureAtRuntime(rdp.texture_to_load.addr,size_bytes);\n    rdp.loaded_texture[rdp.texture_to_load.tile_number].addr = rdp.texture_to_load.addr;')
    # The original game has no SM64 custom stereo commands; projection type identifies flat geometry.
    a=pc.index('#ifdef TARGET_N3DS\n            case G_SPECIAL_1:');b=pc.index('#endif',a)+len('#endif')
    pc=pc[:a]+'''            case G_SPECIAL_1:
                gfx_matrix_mul(rsp.MP_matrix,rsp.modelview_matrix_stack[rsp.modelview_matrix_stack_size-1],rsp.P_matrix);
                break;
            case G_RDPLOADSYNC: case G_RDPPIPESYNC: case G_RDPTILESYNC: case G_RDPFULLSYNC:
            case G_SPNOOP: case G_NOOP: case G_LOAD_UCODE:
                break;
            case G_CULLDL: {
                unsigned first=C0(0,16)/2,last=C1(0,16)/2,planes=63;
                SUPPORT_CHECK(first<=last&&last<MAX_VERTICES);
                for(unsigned i=first;i<=last;i++)planes&=rsp.loaded_vertices[i].clip_rej;
                if(planes){native_dl_leave();return;}
                break;
            }
            default:
                nativeUnknownOpcode(opcode,cmd);
                break;
'''+pc[b:]
    pc=pc.replace('            case G_SETENVCOLOR:', '            case G_SETBLENDCOLOR:\n                rdp.blend_color=cmd->words.w1;break;\n            case G_SETPRIMDEPTH:\n                rdp.prim_depth=cmd->words.w1;break;\n            case G_SETENVCOLOR:')
    pc=pc.replace('    if (parameters & G_MTX_PROJECTION) {','    if (parameters & G_MTX_PROJECTION) {\n        gfx_flush();')
    pc=pc.replace('    gfx_matrix_mul(rsp.MP_matrix, rsp.modelview_matrix_stack[rsp.modelview_matrix_stack_size - 1], rsp.P_matrix);\n}', '    gfx_matrix_mul(rsp.MP_matrix, rsp.modelview_matrix_stack[rsp.modelview_matrix_stack_size - 1], rsp.P_matrix);\n    if((parameters & G_MTX_PROJECTION)&&(parameters & G_MTX_LOAD))gfx_rapi->set_2d(!nativeStereoLoadProjection(addr));\n}')
    pc=pc.replace('    rdp.viewport = default_viewport;', '    gfx_flush();gfx_rapi->set_2d(1);\n    rdp.viewport = default_viewport;')
    pc=pc.replace('    rsp.geometry_mode = geometry_mode_saved;', '    gfx_flush();gfx_rapi->set_2d(!native_stereo_perspective);\n    rsp.geometry_mode = geometry_mode_saved;')
    # Repeated display-list state commands do not need to split a triangle
    # batch. Preserve ordering when the effective value actually changes.
    pc=pc.replace('    gfx_flush();\n    uint64_t mask =', '    uint64_t mask =')
    pc=pc.replace('    om = (om & ~mask) | mode;', '    uint64_t next=(om & ~mask) | mode;\n    if(next==om)return;\n    gfx_flush();om=next;')
    for name in ['env','prim']:
        needle='    if(rdp.'+name+'_color.r!=r||rdp.'+name+'_color.g!=g||rdp.'+name+'_color.b!=b||rdp.'+name+'_color.a!=a)gfx_flush();'
        pc=pc.replace(needle,'    if(rdp.'+name+'_color.r==r&&rdp.'+name+'_color.g==g&&rdp.'+name+'_color.b==b&&rdp.'+name+'_color.a==a)return;\n    gfx_flush();')
    pc=pc.replace('    gfx_sp_reset();','    gfx_sp_reset();\n    nativeDlFrameBegin();')
    pc=function(pc,'gfx_dp_load_tlut','''    SUPPORT_CHECK(tile<8 && rdp.tile_tmem[tile]>=256);
    unsigned offset=(rdp.tile_tmem[tile]-256)*2,bytes=((high_index+1)*2+7)&~7;
    SUPPORT_CHECK(offset<512 && bytes<=512-offset);
    portRelocFixupTextureAtRuntime(rdp.texture_to_load.addr,bytes);
    memcpy(rdp.palette_data+offset,rdp.texture_to_load.addr,bytes);
    rdp.palette=rdp.palette_data;
    uint32_t hash=2166136261u;
    for(unsigned i=0;i<512;i++)hash=(hash^rdp.palette_data[i])*16777619u;
    rdp.palette_hash=hash;rdp.textures_changed[0]=rdp.textures_changed[1]=true;''')
    pc=function(pc,'gfx_dp_load_block','''    SUPPORT_CHECK(tile<8 && uls==0 && ult==0);
    unsigned slot=rdp.tile_tmem[tile]/256,bits=4u<<rdp.texture_to_load.siz;
    unsigned bytes=((lrs+1)*bits+7)/8;
    SUPPORT_CHECK(slot<2 && bytes<=4096);
    portRelocFixupTextureAtRuntime(rdp.texture_to_load.addr,bytes);
    rdp.loaded_texture[slot].addr=rdp.texture_to_load.addr;
    rdp.loaded_texture[slot].pixels=rdp.texture_to_load.addr;
    rdp.loaded_texture[slot].size_bytes=bytes;
    rdp.textures_changed[slot]=true;''')
    pc=function(pc,'gfx_dp_load_tile','''    SUPPORT_CHECK(tile<8 && lrs>=uls && lrt>=ult);
    unsigned slot=rdp.tile_tmem[tile]/256,bits=4u<<rdp.texture_to_load.siz;
    unsigned x=uls>>2,y=ult>>2,w=((lrs-uls)>>2)+1,h=((lrt-ult)>>2)+1;
    unsigned stride=(rdp.texture_to_load.width*bits+7)/8,rowbytes=(w*bits+7)/8;
    unsigned pitch=rdp.tile_line[tile]?(rdp.tile_line[tile]*(bits==32?2:1)):rowbytes;
    unsigned offset=y*stride+x*bits/8;
    if(!(slot<2 && pitch>=rowbytes && pitch*h<=4096 && !((x*bits)&7)))nativeTextureLoadDiagnostic(tile,slot,bits,x,y,w,h,stride,rowbytes,pitch);
    SUPPORT_CHECK(slot<2 && pitch>=rowbytes && pitch*h<=4096 && !((x*bits)&7));
    const uint8_t* source=rdp.texture_to_load.addr+offset;
    portRelocFixupTextureAtRuntime(rdp.texture_to_load.addr,offset+(h-1)*stride+rowbytes);
    uint8_t* staging=rdp.loaded_texture[slot].staging;
    for(unsigned row=0;row<h;row++){
        memcpy(staging+row*pitch,source+row*stride,rowbytes);
        memset(staging+row*pitch+rowbytes,0,pitch-rowbytes);
    }
    rdp.loaded_texture[slot].addr=source;
    rdp.loaded_texture[slot].pixels=staging;
    rdp.loaded_texture[slot].size_bytes=pitch*h;
    rdp.texture_tile.uls=uls;rdp.texture_tile.ult=ult;
    rdp.texture_tile.lrs=lrs;rdp.texture_tile.lrt=lrt;
    rdp.textures_changed[slot]=true;''')
    # Import decoders consume staged pixels; cache keys keep the original DRAM address.
    a=pc.index('static void import_texture_rgba16');b=pc.index('static void import_texture(int tile)',a)
    pc=pc[:a]+pc[a:b].replace('rdp.loaded_texture[tile].addr','rdp.loaded_texture[tile].pixels')+pc[b:]
    pc=pc.replace('            case G_VTX:', '''            case G_MODIFYVTX: {
                unsigned idx=C0(1,15),where=C0(16,8);SUPPORT_CHECK(idx<MAX_VERTICES);
                struct LoadedVertex* v=&rsp.loaded_vertices[idx];
                if(where==G_MWO_POINT_ST){v->u=(int16_t)C1(16,16);v->v=(int16_t)C1(0,16);}
                else if(where==G_MWO_POINT_RGBA){v->color=(struct RGBA){C1(24,8),C1(16,8),C1(8,8),C1(0,8)};}
                else nativeUnknownOpcode(0x0200|where,cmd);
                break;
            }
            case G_VTX:''')
    # Cache identity must include the palette and dimensions, and scene arena reuse must invalidate it.
    pc=pc.replace('    uint8_t fmt, siz;', '    uint8_t fmt, siz;\n    const void* palette;\n    uint32_t bytes,line,palette_hash;')
    pc=pc.replace('(*node)->siz == siz)', '(*node)->siz == siz && (*node)->palette==rdp.palette && (*node)->bytes==rdp.loaded_texture[tile].size_bytes && (*node)->line==rdp.texture_tile.line_size_bytes)')
    pc=pc.replace('    (*node)->siz = siz;', '    (*node)->siz = siz;\n    (*node)->palette=rdp.palette;(*node)->bytes=rdp.loaded_texture[tile].size_bytes;(*node)->line=rdp.texture_tile.line_size_bytes;')
    pc=pc.replace('(*node)->palette==rdp.palette', '(*node)->palette==rdp.palette && (*node)->palette_hash==rdp.palette_hash')
    pc=pc.replace('(*node)->palette=rdp.palette;', '(*node)->palette=rdp.palette;(*node)->palette_hash=rdp.palette_hash;')
    pc+='''
void portTextureCacheDeleteRange(const void* base,size_t size) {
    uintptr_t lo=(uintptr_t)base;
    for(unsigned i=0;i<gfx_texture_cache.pool_pos;i++) {
        struct TextureHashmapNode* n=&gfx_texture_cache.pool[i];
        if(((uintptr_t)n->texture_addr>=lo && (uintptr_t)n->texture_addr-lo<size) || ((uintptr_t)n->palette>=lo && (uintptr_t)n->palette-lo<size)) n->fmt=255;
    }
    rdp.textures_changed[0]=rdp.textures_changed[1]=true;
}
'''
    pc=pc.replace('portRelocFixupTextureAtRuntime(', 'nativeFixTexture(').replace('portRelocFixupVertexAtRuntime(', 'nativeFixVertices(')
    packed=lambda name:'rdp.'+name+'_color.r|((uint32_t)rdp.'+name+'_color.g<<8)|((uint32_t)rdp.'+name+'_color.b<<16)|((uint32_t)rdp.'+name+'_color.a<<24)'
    update='nativeSetSecondCycle(rdp.combine_raw[0],rdp.combine_raw[1],rdp.other_mode_h,'+packed('env')+','+packed('prim')+');'
    pc=pc.replace('case G_SETCOMBINE:\n', 'case G_SETCOMBINE:\n                gfx_flush();\n')
    pc=pc.replace('rdp.combine_raw[1]=cmd->words.w1;', 'rdp.combine_raw[1]=cmd->words.w1;'+update)
    pc=pc.replace('rdp.other_mode_h = (uint32_t)(om >> 32);', 'rdp.other_mode_h = (uint32_t)(om >> 32);'+update)
    pc=pc.replace('rdp.env_color.a = a;', 'rdp.env_color.a = a;'+update)
    pc=pc.replace('rdp.prim_color.a = a;', 'rdp.prim_color.a = a;'+update)
    pc=pc.replace('    uint64_t cc_id = rdp.combine_mode;', '    uint64_t cc_id = rdp.combine_mode;\n    if(native_second_needs_shade)cc_id|=1ull<<36;')
    pc=pc.replace('    comb->cc_id = cc_id;', '''    if(cc_id&(1ull<<36)) {
        unsigned index=0;
        while(index<4&&shader_input_mapping[0][index]!=CC_SHADE&&shader_input_mapping[0][index]!=0)index++;
        SUPPORT_CHECK(index<4);
        shader_input_mapping[0][index]=CC_SHADE;
        if(!shader_input_mapping[1][index])shader_input_mapping[1][index]=CC_SHADE;
        shader_id=(shader_id&0x0fffffffu)|((index+1)<<28);
    }
    comb->cc_id = cc_id;''')
    pc=pc.replace('memset(&tmp, 0, sizeof(tmp));', 'memset(&tmp, 0, sizeof(tmp));if(k==1&&j==0)tmp.a=v_arr[i]->color.a;')
    pc=pc.replace('uint32_t blend_color,prim_depth,combine_raw[2];','uint32_t blend_color,prim_depth,combine_raw[2];\n    uint8_t prim_lod;')
    pc=pc.replace('        case G_CCMUX_1:', '        case G_CCMUX_PRIM_LOD_FRAC:\n            return CC_PRIMLOD;\n        case G_CCMUX_1:')
    pc=pc.replace('                case CC_ONE:\n                case CC_LOD:', '                case CC_ONE:\n                case CC_PRIMLOD:\n                case CC_LOD:')
    pc=pc.replace('                    case CC_ONE:', '                    case CC_PRIMLOD:\n                        tmp=(struct RGBA){rdp.prim_lod,rdp.prim_lod,rdp.prim_lod,rdp.prim_lod};color=&tmp;break;\n                    case CC_ONE:')
    pc=pc.replace('static void gfx_dp_set_combine_mode(', '''static uint32_t alpha_comb(uint32_t a,uint32_t b,uint32_t c,uint32_t d) {
    uint32_t middle=c==0?CC_LOD:c==6?CC_PRIMLOD:color_comb_component(c);
    return color_comb_component(a)|(color_comb_component(b)<<4)|(middle<<8)|(color_comb_component(d)<<12);
}

static void gfx_dp_set_combine_mode(''')
    pc=pc.replace('color_comb(C0(12, 3), C1(12, 3), C0(9, 3), C1(9, 3))', 'alpha_comb(C0(12, 3), C1(12, 3), C0(9, 3), C1(9, 3))')
    pc=pc.replace('            case G_SETPRIMCOLOR:', '            case G_SETPRIMCOLOR:\n                if(rdp.prim_lod!=C0(0,8))gfx_flush();rdp.prim_lod=C0(0,8);')
    pc=prepare_texture.frontend(pc)
    pc=prepare_tmem.frontend(pc,function)
    a=pc.index('static void gfx_dp_fill_rectangle');b=pc.index('static void gfx_dp_set_z_image',a)
    block=pc[a:b].replace('    gfx_dp_set_combine_mode(', '    if(mode==G_CYC_FILL)gfx_dp_set_combine_mode(')
    pc=pc[:a]+block+pc[b:]
    pc=prepare_ui.frontend(pc)
    (OUT/'gfx_pc.c').write_text(pc)
    header=(SOURCE/'gfx_cc.h').read_text().replace('    CC_LOD\n','    CC_LOD,\n    CC_ONE,\n    CC_PRIMLOD\n')
    (OUT/'gfx_cc.h').write_text(header)
    backend=(SOURCE/'gfx_citro3d.c').read_text()
    backend=backend.replace('#include "macros.h"','#include "native_render_macros.h"')
    backend=backend.replace('#include "gfx_3ds_menu.h"','').replace('#include "gfx_citro3d.h"','').replace('#include "color_conversion.h"','')
    a=backend.index('// Data storage type');b=backend.index('void stereoTilt',a)
    backend=backend[:a]+backend[b:]
    backend=function(backend,'stereoTilt','''    Mtx_Identity(mtx);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,uLoc_projection,mtx);
    float shift=(!s2DMode&&z!=0.0f)?(z<0?-1.0f:1.0f)*gSliderLevel*NATIVE_STEREO_SHIFT_MAX:0.0f;
    C3D_FVUnifSet(GPU_VERTEX_SHADER,uLoc_eye,shift,-shift*native_stereo_focus_w,0,0);''')
    backend=backend.replace('sShaderProgramPool[32]','sShaderProgramPool[512]').replace('uint8_t sShaderProgramPoolSize','uint16_t sShaderProgramPoolSize')
    backend=backend.replace('    int id = sShaderProgramPoolSize;', '    if(sShaderProgramPoolSize>=512)abort();\n    int id = sShaderProgramPoolSize;')
    backend=backend.replace('        printf("Out of textures!\\n");\n        return 0;','        abort();')
    backend=backend.replace('    C3D_TexInit(&sTexturePool[sCurTex], width, height, GPU_RGBA8);','    if(sTexturePool[sCurTex].data)C3D_TexDelete(&sTexturePool[sCurTex]);\n    if(!C3D_TexInit(&sTexturePool[sCurTex], width, height, GPU_RGBA8))abort();')
    backend=backend.replace('realX -= width','realX %= width').replace('realY -= height','realY %= height')
    # When BOTH inputs are constant, input 1 still belongs on the vertex and
    # input 2 in the stage constant. The upstream test chose input 2 twice.
    backend=backend.replace('        if (color0Constant)\n            vtxOffs +=', '        if (!color1Constant)\n            vtxOffs +=')
    backend=backend.replace('    update_shader(!color1Constant);', '    unsigned shadeInput=sShaderProgramPool[sCurShader].shader_id>>28;\n    if(shadeInput)color1Constant=shadeInput==1;\n    update_shader(!color1Constant);')
    backend=backend.replace('        if (!color1Constant)\n            vtxOffs += hasAlpha ? 4 : 3;', '        vtxOffs+=(shadeInput?shadeInput-1:(!color1Constant?1:0))*(hasAlpha?4:3);')
    backend=backend.replace('    C3D_FrameRate(30);','    C3D_FrameRate(60);')
    backend=backend.replace('C3D_SetViewport(viewport_y, viewport_x, viewport_height, viewport_width)', 'C3D_SetViewport(viewport_y, viewport_x+40, viewport_height, viewport_width)')
    backend=backend.replace('C3D_SetScissor(GPU_SCISSOR_NORMAL, scissor_y, scissor_x, scissor_height, scissor_width)', 'C3D_SetScissor(GPU_SCISSOR_NORMAL, scissor_y, scissor_x+40, scissor_height, scissor_width+40)')
    backend=backend.replace('    uLoc_projection = shaderInstanceGetUniformLocation', '    uLoc_eye=shaderInstanceGetUniformLocation(sShaderProgram.vertexShader,"eye");\n    uLoc_projection = shaderInstanceGetUniformLocation')
    backend=backend.replace('    if (sBufIdx * VERTEX_SHADER_SIZE > 1 * 1024 * 1024 / 4)','    if ((sBufIdx + buf_vbo_num_tris*3) * VERTEX_SHADER_SIZE > 1 * 1024 * 1024 / 4)')
    backend=backend.replace('        printf("Vertex buffer full!\\n");\n        return;', '        port_log("Vertex buffer exhausted\\n");abort();')
    backend=backend.replace('static uint32_t fog_color;', 'static uint32_t fog_color;\nint native_fog_primitive;')
    backend=backend.replace('#define FOG_LUT_SIZE 32','#define FOG_LUT_SIZE 256').replace('static uint8_t fog_lut_size;','static uint16_t fog_lut_size;')
    backend=backend.replace('        printf("Fog exhausted!\\n");\n        return;', '        port_log("Fog LUT cache exhausted\\n");abort();')
    backend=backend.replace('    // FIXME: The near/far factors are personal preference\n    // BOB:  6400, 59392 => 0.16, 116\n    // JRB:  1280, 64512 => 0.80, 126\n','')
    backend=backend.replace('if (fog_lut[current_fog_idx].id == id)', 'if (fog_lut_size && fog_lut[current_fog_idx].id == id)')
    backend=backend.replace('FogLut_Exp(&fog_lut[current_fog_idx].lut, 0.05f, 1.5f, 1024 / (float)from, ((float)to) / 512);', '''/* FogFactor is signed, linear in N64 clip Z/W. PICA's enabled Z flip
     * indexes this LUT with 1-depth, where depth=(N64_Z/W+1)/2.
     * Cache the resulting visibility curve; both eyes use the same LUT. */
    float data[256];
    for(unsigned i=0;i<=128;i++){
        float z=1.0f-i/64.0f;
        float amount=(z*(int16_t)from+(int16_t)to)/255.0f;
        float visibility=1.0f-fminf(1.0f,fmaxf(0.0f,amount));
        if(i<128)data[i]=visibility;
        if(i)data[i+127]=visibility-data[i-1];
    }
    FogLut_FromArray(&fog_lut[current_fog_idx].lut,data);''')
    backend=backend.replace('#include "gfx_rendering_api.h"', '#include "gfx_rendering_api.h"\n#include "native_second_cycle.h"')
    backend=backend.replace('static bool gfx_citro3d_z_is_from_0_to_1', '#include "native_render_queue.h"\n\nstatic bool gfx_citro3d_z_is_from_0_to_1')
    backend=backend.replace('C3D_TexDelete(&sTexturePool[sCurTex])','nativeRetireTexture(&sTexturePool[sCurTex])')
    backend=backend.replace('C3D_DrawArrays(GPU_TRIANGLES, sBufIdx, buf_vbo_num_tris * 3);','nativeQueueDraw(sBufIdx,buf_vbo_num_tris*3);')
    backend=backend.replace('C3D_FrameBegin(C3D_FRAME_SYNCDRAW);','uint64_t waitStart=svcGetSystemTick();\n    C3D_FrameBegin(C3D_FRAME_SYNCDRAW);\n    native_perf_render.wait_ms=(svcGetSystemTick()-waitStart)*(1000.0f/SYSCLOCK_ARM11);\n    nativeQueueBegin();')
    # The frontend retains the N64 scissor across frames and only sends changes.
    # Resetting this flag silently disabled an unchanged gameplay scissor, letting
    # the background sprite spill into the bottom overscan border.
    backend=backend.replace('    scissor = false;', '    /* Preserve the frontend-cached scissor across frames. */')
    backend=backend.replace('    C3D_FrameEnd(0);', '    nativeQueueRender();\n    C3D_FrameEnd(0);')
    backend=backend.replace('    C3D_FrameEnd(0);', '    GSPGPU_FlushDataCache(sVboBuffer,(sBufIdx*VERTEX_SHADER_SIZE*4+31)&~31);\n    C3D_FrameEnd(GX_CMDLIST_FLUSH);')
    backend=backend.replace('C3D_FrameEnd(GX_CMDLIST_FLUSH);','C3D_FrameEnd(GX_CMDLIST_FLUSH);\n    nativeQueueEnd();\n    native_perf_render.submit_ms=C3D_GetProcessingTime();')
    backend=function(backend,'gfx_citro3d_draw_triangles_helper','''    int first=sBufIdx;
    nativeApplySecondCycle();
    C3D_TexEnv* fog=C3D_GetTexEnv(5);
    C3D_TexEnvInit(fog);
    if(native_fog_primitive && (fog_color>>24)) {
        C3D_TexEnvColor(fog,fog_color);
        C3D_TexEnvFunc(fog,C3D_RGB,GPU_INTERPOLATE);
        C3D_TexEnvSrc(fog,C3D_RGB,GPU_CONSTANT,GPU_PREVIOUS,GPU_CONSTANT);
        C3D_TexEnvOpRgb(fog,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_ALPHA);
    }
    gfx_citro3d_draw_triangles(buf_vbo,buf_vbo_len,buf_vbo_num_tris);
    ''')
    backend=backend.replace('    clear_buffers();', '    /* Clear in nativeQueueRender after classifying flat/stereo output. */')
    backend=backend.replace('    gfx_citro3d_set_viewport_clear_buffer(VIEW_MAIN_SCREEN, VIEW_CLEAR_BUFFER_DEPTH);','')
    backend=backend.replace('    screen_clear_bufs.struc.top = \n    screen_clear_bufs.struc.bottom = VIEW_CLEAR_BUFFER_NONE;','')
    backend=backend.replace('    gfx_3ds_menu_draw(sVboBuffer, sBufIdx, gShowConfigMenu);','')
    a=backend.index('void gfx_citro3d_set_clear_color(');b=backend.index('struct GfxRenderingAPI gfx_citro3d_api',a)
    backend=backend[:a]+backend[b:]
    backend=backend.replace('    if (sShaderProgramPool[sCurShader].cc_features.opt_fog)\n        C3D_TexEnvColor(C3D_GetTexEnv(2), vec4ToU32Color(buf_vbo[hasTex ? 6 : 4], buf_vbo[hasTex ? 7 : 5], buf_vbo[hasTex ? 8 : 6], buf_vbo[hasTex ? 9 : 7]));','')
    backend=prepare_texture.backend(backend)
    backend=prepare_tmem.backend(backend)
    (OUT/'gfx_citro3d.c').write_text(backend)
    shader=(SOURCE/'shader.v.pica').read_text().replace('.fvec projection[4], modelView[4]','.fvec projection[4], modelView[4], eye')
    shader=shader.replace('    mov r0, inpos','    mov r0, inpos\n    mul r2.x, eye.x, inpos.w\n    add r0.x, r2.x, inpos.x\n    add r0.x, eye.y, r0.x')
    shader=shader.replace('mov outtc1, intex','mov outtc1, intex.zwzz')
    (OUT/'shader.v.pica').write_text(shader)
    cc=(SOURCE/'gfx_cc.c').read_text().replace('    cc_features->do_single[0]', '    unsigned forced=shader_id>>28;\n    if(forced>cc_features->num_inputs)cc_features->num_inputs=forced;\n    cc_features->do_single[0]',1)
    (OUT/'gfx_cc.c').write_text(cc)
if __name__=='__main__':main()

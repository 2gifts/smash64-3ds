"""RDP rectangle coverage and depth masks used by Smash's interface."""
def frontend(pc):
    pc=pc.replace('static size_t buf_vbo_len;', 'static int nativeRectangle;\nstatic unsigned nativeMaskPending,nativeMaskNext;\nstatic size_t buf_vbo_len;')
    pc=pc.replace('gfx_flush();gfx_rapi->set_2d(1);', 'gfx_flush();nativeRectangle=1;gfx_rapi->set_2d(1);')
    pc=pc.replace('gfx_flush();gfx_rapi->set_2d(!native_stereo_perspective);', 'gfx_flush();nativeRectangle=0;gfx_rapi->set_2d(!native_stereo_perspective);')
    # Rectangle vertices describe pixel boundaries. Interpolation already adds
    # the half texel at pixel centers; adding it again blurs short UI lettering.
    pc=pc.replace('if((rdp.other_mode_h&(3u<<G_MDSFT_TEXTFILT))!=G_TF_POINT){u+=0.5f;v+=0.5f;}',
        'if(!nativeRectangle&&(rdp.other_mode_h&(3u<<G_MDSFT_TEXTFILT))!=G_TF_POINT){u+=0.5f;v+=0.5f;}')
    pc=pc.replace('    bool use_alpha =', '    native_alpha_threshold=(rdp.other_mode_l&3)==G_AC_THRESHOLD?(rdp.blend_color&255):0;\n    bool use_alpha =')
    pc=pc.replace('    if (texture_edge) {', '    if (texture_edge || native_alpha_threshold) {')
    pc=pc.replace('rdp.blend_color=cmd->words.w1;', 'gfx_flush();rdp.blend_color=cmd->words.w1;')
    pc=pc.replace('    unsigned saved_tile=rdp.first_tile;', '''    gfx_flush();
    native_depth_mask=rdp.color_image_address==rdp.z_buf_address;
    if(native_depth_mask){
        SUPPORT_CHECK(++nativeMaskNext<255);
        native_stencil_ref=nativeMaskNext;
    }
    unsigned saved_tile=rdp.first_tile;''')
    pc=pc.replace('    rdp.first_tile=saved_tile;', '''    if(native_depth_mask){
        nativeMaskPending=native_stencil_ref;
        native_depth_mask=0;native_stencil_ref=0;
    }
    rdp.first_tile=saved_tile;''')
    pc=pc.replace('->z = -1.0f;', '->z = native_depth_mask?1.0f:-1.0f;')
    pc=pc.replace('static void gfx_calc_and_set_viewport(const Vp_t *viewport) {', '''static void gfx_calc_and_set_viewport(const Vp_t *viewport) {
    gfx_flush();
    /* The viewport following a Z-mask draws the miniature. Restoring the
     * main camera also ends that mask's scope, before its arrow and HUD. */
    native_stencil_ref=nativeMaskPending;nativeMaskPending=0;''')
    pc=pc.replace('    nativeDlFrameBegin();', '    nativeDlFrameBegin();\n    nativeMaskPending=nativeMaskNext=0;native_depth_mask=native_stencil_ref=0;')
    return pc

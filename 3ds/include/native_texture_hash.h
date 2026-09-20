/* Preserve the existing content fingerprint while using aligned ARM word
 * loads for our TMEM/palette storage. memcpy from an unknown byte alignment
 * otherwise becomes four byte loads and shifts for every word on ARM11. */
static uint32_t nativeTextureHash(const uint8_t* data,unsigned size){
    uint32_t hash=2166136261u;
    if(!((uintptr_t)data&3)){
        const uint32_t* words=(const uint32_t*)data;
        while(size>=16){
            hash=(hash^words[0])*16777619u;
            hash=(hash^words[1])*16777619u;
            hash=(hash^words[2])*16777619u;
            hash=(hash^words[3])*16777619u;
            words+=4;size-=16;
        }
        while(size>=4){hash=(hash^*words++)*16777619u;size-=4;}
        data=(const uint8_t*)words;
    }else{
        while(size>=4){uint32_t word;memcpy(&word,data,4);hash=(hash^word)*16777619u;data+=4;size-=4;}
    }
    while(size--)hash=(hash^*data++)*16777619u;
    return hash;
}

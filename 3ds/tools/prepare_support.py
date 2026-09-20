"""Generate narrow adaptations of the pinned asset bridges to local ROM reads."""
from pathlib import Path
import re
from build import ROOT, UPSTREAM

def write(name, text):
    path=ROOT/'generated'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8')!=text:
        path.write_text(text,encoding='utf-8')

def bridges():
    for name in ['lbreloc_bridge','audio_bridge','particle_bank_bridge']:
        s=(UPSTREAM/'port/bridge'/f'{name}.cpp').read_text(encoding='utf-8')
        s=re.sub(r'^#include <ship/[^\n]+\n','',s,flags=re.M)
        s='#include "native_assets.h"\n'+s
        if name=='lbreloc_bridge':
            a=s.index('static std::shared_ptr<RelocFile> portLoadRelocResource(')
            b=s.index('// All game-facing functions have C linkage',a)
            s=s[:a]+'''static std::shared_ptr<RelocFile> portLoadRelocResource(u32 file_id)
{
    return nativeLoadReloc(file_id);
}

'''+s[b:]
            a=s.index('size_t lbRelocGetExternBytesNum(');b=s.index('size_t lbRelocGetFileSize(',a)
            block=s[a:b].replace('auto relocFile = portLoadRelocResource(file_id);','auto info = nativeRelocInfo(file_id);')
            block=block.replace('if (!relocFile) { return 0; }','').replace('relocFile->Data.size()','info.size')
            block=block.replace('for (u16 dep_id : relocFile->ExternFileIds)','for (unsigned dep=0;dep<info.count;dep++)').replace('lbRelocGetExternBytesNum(dep_id)','lbRelocGetExternBytesNum(info.deps[dep])')
            s=s[:a]+block+s[b:]
        elif name=='audio_bridge':
            s=s.replace('std::shared_ptr<Ship::IResource> resource;',
                        'std::shared_ptr<std::vector<uint8_t>> resource;')
            a=s.index('    auto ctx = Ship::Context::GetInstance();',s.index('static bool loadBlob('))
            b=s.index('    spdlog::info(',a)
            s=s[:a]+'''    auto data = nativeLoadBlob(name);
    if (!data) return false;
    out.data = data->data();
    out.size = data->size();
    out.resource = data;
'''+s[b:]
        else:
            a=s.index('    auto ctx = Ship::Context::GetInstance();',s.index('static const std::vector<uint8_t> *ensurePristine('))
            b=s.index('    if (is_script_bank)',a)
            s=s[:a]+'''    auto blob = nativeLoadBlob(archive_path);
    if (!blob) return nullptr;
    std::vector<uint8_t> data(*blob);
'''+s[b:]
        write(name+'.cpp',s)

if __name__=='__main__':
    bridges()

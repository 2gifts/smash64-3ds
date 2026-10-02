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

    byteswap()

def byteswap():
    """Ordered fixup trackers, so evicting a range costs what it removes.

    The trackers are pure membership sets. Range eviction walked every element
    of five hash containers, and each asset load evicts its destination: the
    Fighting Polygon intro reloads fighter animations about 30 times per frame
    (the original draws each polygon in three poses), which spent ~15 ms per
    frame (emulator) in these walks. Ordered containers keep the same
    membership answers and erase exactly [lo, hi) directly."""
    s=(UPSTREAM/'port/bridge/lbreloc_byteswap.cpp').read_text(encoding='utf-8')
    def sub(a,b):
        nonlocal s
        if s.count(a)!=1:raise ValueError(a[:60])
        s=s.replace(a,b)
    for name in ('sStructU16Fixups','sTexFixupWords','sDeswizzle4cFixups','sChainSlotAddrs'):
        sub(f'static std::unordered_set<uintptr_t> {name};',f'static std::set<uintptr_t> {name};')
    sub('static std::unordered_map<uintptr_t, unsigned int> sTexFixupExtent;','static std::map<uintptr_t, unsigned int> sTexFixupExtent;')
    sub("""	auto evict_set = [&](std::unordered_set<uintptr_t> &s) {
		for (auto it = s.begin(); it != s.end(); ) {
			if (*it >= lo && *it < hi) it = s.erase(it);
			else ++it;
		}
	};""","""	auto evict_set = [&](std::set<uintptr_t> &s) {
		s.erase(s.lower_bound(lo), s.lower_bound(hi));
	};""")
    sub("""	for (auto it = sTexFixupExtent.begin(); it != sTexFixupExtent.end(); ) {
		if (it->first >= lo && it->first < hi) it = sTexFixupExtent.erase(it);
		else ++it;
	}""","""	sTexFixupExtent.erase(sTexFixupExtent.lower_bound(lo), sTexFixupExtent.lower_bound(hi));""")
    sub('#include <unordered_set>\n','#include <unordered_set>\n#include <set>\n#include <map>\n')
    write('lbreloc_byteswap.cpp',s)

if __name__=='__main__':
    bridges()

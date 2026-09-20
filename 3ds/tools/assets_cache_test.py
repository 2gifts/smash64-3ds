"""Exercise the real pristine-asset cache with a tiny synthetic pack."""
import json,struct,subprocess,os
from build import ROOT,OUT,BIN
def main():
    d=OUT/'asset-cache-test';d.mkdir(exist_ok=True)
    data=bytearray(b'SSB3DPAK'+struct.pack('<II',1,2132));offset=16+2132*20
    for i in range(2132):data+=struct.pack('<IIIHHI',offset+i*524288 if i<3 else 0,524288 if i<3 else 0,0,0,0,0)
    for i in range(3):data+=bytes([i+1])*524288
    (d/'reloc.pak').write_bytes(data)
    (d/'reloc-deps.bin').write_bytes(b'SSB3DIDX'+struct.pack('<II',2132,0)+bytes(2133*4))
    source='''#include <memory>
#include <vector>
#include <string>
#include <cstdint>
#include <cassert>
#include <cstdio>
struct RelocFile {uint32_t FileId;uint16_t RelocInternOffset,RelocExternOffset;std::vector<uint8_t> Data;std::vector<uint16_t> ExternFileIds;};
struct NativeRelocInfo {uint32_t size,count;const uint16_t* deps;};
extern "C" {uint32_t native_asset_reads,native_asset_hits,native_asset_bytes;void port_log(const char*,...) {}}
'''+(ROOT/'src/native_assets.cpp').read_text().replace('#include "native_assets.h"','').replace('romfs:/reloc.pak',(d/'reloc.pak').as_posix()).replace('romfs:/reloc-deps.bin',(d/'reloc-deps.bin').as_posix())
    source+='''
int main(){
    for(unsigned i=0;i<500;i++){auto info=nativeRelocInfo(i%3);assert(info.size==524288&&!info.count);}
    assert(native_asset_reads==1&&residentPack);
    auto a=nativeLoadReloc(0);assert(a->Data.size()==524288&&a->Data[0]==1);a.reset();
    auto b=nativeLoadReloc(1);b.reset();
    a=nativeLoadReloc(0);auto copy=a->Data;copy[0]=99;a.reset();
    auto c=nativeLoadReloc(2);c.reset();assert(retainedBytes==1024*1024);
    a=nativeLoadReloc(0);assert(a->Data[0]==1&&native_asset_reads==1&&native_asset_hits==2);a.reset();
    b=nativeLoadReloc(1);assert(b->Data[0]==2&&native_asset_reads==1);b.reset();
    for(unsigned i=0;i<100;i++){auto p=nativeLoadReloc(i%3);assert(p->Data[0]==i%3+1);assert(retainedBytes<=1024*1024);}
    nativeAssetsShutdown();assert(retainedBytes==0&&!pack&&!residentPack&&!packReady);
    openPack();std::free(residentPack);residentPack=nullptr;pack=std::fopen("PACK_PATH","rb");
    unsigned before=native_asset_reads;auto fallback=nativeLoadReloc(0);
    assert(fallback->Data[0]==1&&native_asset_reads==before+1);fallback.reset();nativeAssetsShutdown();
    puts("Allocation fallback, cache hits, pristine copies, LRU eviction, resident-pack reads, 1 MiB decoded-cache bound, repeated reload and shutdown passed");
}
'''
    source=source.replace('PACK_PATH',(d/'reloc.pak').as_posix())
    c=d/'cache.cpp';c.write_text(source);exe=d/'cache.exe'
    p=subprocess.run([str(BIN/'clang++.exe'),'-O2','-I'+str(ROOT/'include'),str(c),'-o',str(exe)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    env=dict(os.environ);env['PATH']=str(BIN)+os.pathsep+env['PATH']
    r=subprocess.run([str(exe)],check=True,capture_output=True,text=True,env=env,timeout=20)
    result=dict(passed=True,detail=r.stdout.strip());(d/'verified.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()

"""Check CIA hashes, executable bytes, capabilities, and every packaged asset."""
import hashlib
import json
import struct
import subprocess
from build import OUT,BIN

def u32(data,off):return struct.unpack_from('<I',data,off)[0]
def align(n,size=64):return (n+size-1)&-size
def sha(data):return hashlib.sha256(data).digest()
def blz(data):
    extra=u32(data,len(data)-4)
    if not extra:return data[:-4]
    info=u32(data,len(data)-8);assert 8<=info>>24<=11
    end=len(data)-(info&0xffffff);src=len(data)-(info>>24)
    out=bytearray(data)+bytearray(extra);dst=len(out)
    while src>end:
        src-=1;flags=out[src]
        for bit in range(7,-1,-1):
            if src<=end:break
            if flags&(1<<bit):
                src-=2;token=out[src]|out[src+1]<<8
                count,distance=(token>>12)+3,(token&4095)+3
                for _ in range(count):
                    dst-=1;assert end<=dst<dst+distance<len(out)
                    out[dst]=out[dst+distance]
            else:
                src-=1;dst-=1;out[dst]=out[src]
    assert dst==end
    return bytes(out)

def main():
    folder=OUT/'package';raw=(folder/'smash64-development.cia').read_bytes()
    hdr,_,_,cert,ticketSize,tmdSize,metaSize,size=struct.unpack_from('<IHHIIIIQ',raw)
    assert hdr==0x2020 and raw[0x20]==0x80
    tp=align(hdr)+align(cert);mp=tp+align(ticketSize);cp=mp+align(tmdSize)
    assert cp+align(size)+metaSize==len(raw)
    ticket=raw[tp:tp+ticketSize];tmd=raw[mp:mp+tmdSize];content=raw[cp:cp+size]
    title=0x000400000ff64000
    assert int.from_bytes(ticket[0x1dc:0x1e4],'big')==title
    assert int.from_bytes(tmd[0x18c:0x194],'big')==title
    title_version=int.from_bytes(tmd[0x1dc:0x1de],'big')
    assert title_version==8
    assert int.from_bytes(tmd[0x1de:0x1e0],'big')==1
    chunk=tmd[0xb04:0xb34]
    assert int.from_bytes(chunk[8:16],'big')==size and not int.from_bytes(chunk[6:8],'big')&1
    assert sha(content)==chunk[16:48]
    assert sha(tmd[0x204:0xb04])==tmd[0x1e4:0x204]
    assert content[0x100:0x104]==b'NCCH'
    assert content==(folder/'smash64-development.cxi').read_bytes()
    for off in (0x108,0x118,0x3c8,0x400,0x800):assert struct.unpack_from('<Q',content,off)[0]==title
    assert content[0x18c]==2 and content[0x18f]&4
    exhdr=content[0x200:0x600];assert sha(exhdr)==content[0x160:0x180]
    assert exhdr[0x20c:0x210]==bytes([3,1,4,48])
    offset,pages,hashed=struct.unpack_from('<III',content,0x1a0)
    exefs=content[offset*512:(offset+pages)*512]
    assert sha(exefs[:hashed*512])==content[0x1c0:0x1e0]
    files={}
    for i in range(10):
        name,off,count=struct.unpack_from('<8sII',exefs,i*16)
        if not count:continue
        data=exefs[512+off:512+off+count]
        assert sha(data)==exefs[0xc0+(9-i)*32:0xe0+(9-i)*32]
        files[name.rstrip(b'\0').decode()]=data
    assert set(files)=={'.code','icon','banner','logo'}
    assert len(files['logo'])==8192 and files['logo'][0]==0x11
    for key,suffix in [('icon','smdh'),('banner','bin')]:assert files[key]==(folder/(key+'.'+suffix)).read_bytes()
    elf=(folder/'ssb64-package.elf').read_bytes();assert elf[:6]==b'\x7fELF\x01\x01'
    phoff=u32(elf,28);phentsize,phnum=struct.unpack_from('<HH',elf,42)
    loads=[struct.unpack_from('<8I',elf,phoff+i*phentsize) for i in range(phnum)]
    loads=[p for p in loads if p[0]==1];assert len(loads)==3
    code=blz(files['.code']) if exhdr[13]&1 else files['.code'];cursor=0
    for p,off in zip(loads,(0x10,0x20,0x30)):
        address,pages,count=struct.unpack_from('<III',exhdr,off)
        assert address==p[2] and count==p[4]
        assert code[cursor:cursor+count]==elf[p[1]:p[1]+count]
        cursor+=pages*4096
    assert cursor==len(code) and u32(exhdr,0x3c)==loads[-1][5]-loads[-1][4]
    roff,rpages,rhashed=struct.unpack_from('<III',content,0x1b0)
    romfs=content[roff*512:(roff+rpages)*512]
    assert romfs[:4]==b'IVFC' and sha(romfs[:rhashed*512])==content[0x1e0:0x200]
    level3=align(u32(romfs,84)+u32(romfs,8),1<<u32(romfs,76))
    h=struct.unpack_from('<10I',romfs,level3);assert h[0]==40
    packaged={}
    def visit(offset,parent):
        p=level3+h[3]+offset
        _,sibling,child,file,_,n=struct.unpack_from('<6I',romfs,p)
        name=romfs[p+24:p+24+n].decode('utf-16le');path=parent+'/'+name if parent else name
        while file!=0xffffffff:
            f=level3+h[7]+file
            _,nextFile,dataOff,dataSize,_,nameSize=struct.unpack_from('<IIQQII',romfs,f)
            fn=romfs[f+32:f+32+nameSize].decode('utf-16le');key=path+'/'+fn if path else fn
            start=level3+h[9]+dataOff;data=romfs[start:start+dataSize]
            assert data==(OUT/'romfs'/key).read_bytes(),key
            packaged[key]=len(data);file=nextFile
        if child!=0xffffffff:visit(child,path)
        if sibling!=0xffffffff:visit(sibling,parent)
    visit(0,'')
    expected={p.relative_to(OUT/'romfs').as_posix() for p in (OUT/'romfs').rglob('*') if p.is_file()}
    assert set(packaged)==expected and not any(k.endswith(('.z64','.cdc')) for k in packaged)
    metadata=json.loads((folder/'package.json').read_text())
    defaults={}
    if metadata.get('build_variant')=='release':
        raw_symbols=subprocess.check_output([str(BIN/'llvm-nm.exe'),'-n',str(folder/'ssb64-package.elf')],text=True)
        symbols={parts[2]:int(parts[0],16) for line in raw_symbols.splitlines() if len(parts:=line.split())==3 and all(c in '0123456789abcdefABCDEF' for c in parts[0])}
        wanted={'ssb_test_frame_limit':0,'ssb_test_inputs':0,'ssb_test_logging':0,'ssb_test_metrics':0,'ssb_test_boot_gate':1,'native_test_no_capture':1,'native_test_slider':0xbf800000,'ssb_test_single_stage':0xffffffff,'ssb_test_start_scene':0xffffffff}
        wanted.update(native_test_bottom_disabled=0,native_bottom_page=0,native_test_touch=0,native_widescreen=0,native_test_magnifier_capture=0,native_test_dump_textures=0,native_capture_requested=0,native_test_uncached_state=0)
        wanted.update(native_test_cstick_active=0,native_test_cstick_x=0,native_test_cstick_y=0,native_tap_jump_disabled=0,native_cstick_enabled=0)
        for name,value in wanted.items():
            address=symbols[name];segment=next(p for p in loads if p[2]<=address< p[2]+p[5])
            offset=address-segment[2]
            actual=u32(elf,segment[1]+offset) if offset+4<=segment[4] else 0
            assert actual==value,(name,hex(actual),hex(value));defaults[name]=hex(actual)
    result=dict(development_only=metadata['development_only'],startup_defaults=defaults,title_id=f'{title:016x}',title_version=title_version,cpu_mhz=804,l2=True,memory_mb=124,
        executable_bytes_verified=len(code),assets_verified=packaged,sha256=sha(raw).hex())
    (folder/'verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

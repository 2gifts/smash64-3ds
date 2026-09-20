"""Keep size/dependency planning from reading entire assets on the console."""
import struct
from build import ROOT
def main():
    pack=(ROOT/'assets/reloc.pak').read_bytes();assert pack[:8]==b'SSB3DPAK'
    version,count=struct.unpack_from('<II',pack,8);assert version==1 and count==2132
    offsets=[0];deps=bytearray()
    for i in range(count):
        start,size,n,*_=struct.unpack_from('<IIIHHI',pack,16+i*20)
        chunk=pack[start+size:start+size+n*2];assert len(chunk)==n*2
        deps+=chunk;offsets.append(len(deps)//2)
    data=b'SSB3DIDX'+struct.pack('<II',count,len(deps)//2)+struct.pack('<%dI'%len(offsets),*offsets)+deps
    path=ROOT/'assets/reloc-deps.bin'
    if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
    print('Relocation dependency index:',len(data),'bytes')
if __name__=='__main__':main()

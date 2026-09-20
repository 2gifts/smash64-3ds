"""Extract a checked, indexed, big-endian asset pack from the user's own ROM."""
import hashlib
import importlib.util
import json
import struct
import re
import sys
from pathlib import Path
from build import ROOT,UPSTREAM,CONFIG,configured

ROOT = Path(__file__).resolve().parents[1]
ROM = configured('rom',ROOT/'baserom.us.z64')
SAVE = configured('save',CONFIG['save']) if CONFIG.get('save') else None
EXPECTED = 'e2929e10fccc0aa84e5776227e798abc07cedabf'
EXTRACTOR = UPSTREAM/'debug_tools/reloc_extract/reloc_extract.py'

def chain_slots(data, start):
    seen = set()
    while start != 0xffff:
        if start in seen or start*4+4 > len(data):
            raise ValueError(f'Invalid relocation chain at word {start}')
        seen.add(start)
        word = struct.unpack_from('>I', data, start*4)[0]
        yield start, word & 0xffff
        start = word >> 16

def main():
    rom = ROM.read_bytes()
    if len(rom) != 16777216 or hashlib.sha1(rom).hexdigest() != EXPECTED:
        raise ValueError('ROM does not match the required US 1.0 revision')
    out = ROOT/'assets'
    out.mkdir(parents=True, exist_ok=True)
    blob_manifest=[]
    for group in ['audio','particles']:
        recipe=UPSTREAM/'yamls/us'/f'{group}.yml'
        text=recipe.read_text(encoding='utf-8')
        pattern=r'(?m)^([A-Za-z0-9_]+):\s*\n\s+type: BLOB\s*\n\s+offset: (0x[0-9A-Fa-f]+)\s*\n\s+size: (0x[0-9A-Fa-f]+)'
        rows=re.findall(pattern,text)
        if len(rows)!=text.count('type: BLOB'):
            raise ValueError(f'Unhandled blob recipe in {recipe}')
        for name,begin,size in rows:
            begin,size=int(begin,16),int(size,16)
            if begin+size>len(rom):raise ValueError('Blob beyond ROM end')
            data=rom[begin:begin+size]
            path=out/group/(name+'.bin');path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            blob_manifest.append(dict(name=f'{group}/{name}',offset=begin,size=size,sha256=hashlib.sha256(data).hexdigest()))
    (out/'blobs.json').write_text(json.dumps(blob_manifest,indent=2))
    print(f'Extracted {len(blob_manifest)} audio/particle blobs',flush=True)
    if '--blobs-only' in sys.argv:return
    spec = importlib.util.spec_from_file_location('reloc_extract', EXTRACTOR)
    ext = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ext)
    entries=[]
    data_blobs=[]
    manifest=[]
    offset=16+ext.RELOC_FILE_COUNT*20
    for fid in range(ext.RELOC_FILE_COUNT):
        if fid % 100 == 0:
            print(f'Extracting {fid}/{ext.RELOC_FILE_COUNT}', flush=True)
        info=ext.read_table_entry(rom, fid)
        begin=ext.RELOC_DATA_START+info['data_offset']
        end=ext.RELOC_DATA_START+info['next_data_offset']
        comp_size=info['compressed_bytes']
        if not 0 <= begin <= begin+comp_size <= end <= len(rom):
            raise ValueError(f'Bad ROM bounds for file {fid}')
        raw=rom[begin:begin+comp_size]
        data=ext.vpk0_decode(raw) if info['is_compressed'] else raw
        # The table counts words; compressed streams can end in a partial word.
        expected=info['decompressed_bytes']
        if not expected-3 <= len(data) <= expected:
            raise ValueError(f'Decompressed length mismatch for {fid}: {len(data)} != {expected}')
        data=data.ljust(expected,b'\0')
        intern=list(chain_slots(data,info['reloc_intern']))
        external=list(chain_slots(data,info['reloc_extern']))
        ids_be=rom[begin+comp_size:begin+comp_size+len(external)*2]
        if begin+comp_size+len(ids_be)>end or len(ids_be)!=len(external)*2:
            raise ValueError(f'External dependency table out of bounds for {fid}')
        ids=list(struct.unpack('>'+str(len(external))+'H',ids_be))
        if any(x>=ext.RELOC_FILE_COUNT for x in ids):
            raise ValueError(f'Invalid external file identifier for {fid}')
        if any(target*4>=len(data) for _,target in intern):
            raise ValueError(f'Invalid internal relocation target for {fid}')
        dep_bytes=struct.pack('<'+str(len(ids))+'H',*ids)
        payload=data+dep_bytes
        entries.append(struct.pack('<IIIHHI',offset,len(data),len(ids),info['reloc_intern'],info['reloc_extern'],0))
        data_blobs.append(payload)
        offset+=len(payload)
        manifest.append(dict(id=fid,size=len(data),sha256=hashlib.sha256(data).hexdigest(),
                             internal_slots=len(intern),external_files=ids))
    for fid,entry in enumerate(manifest):
        data=data_blobs[fid][:entry['size']]
        info=ext.read_table_entry(rom,fid)
        for (_,target),dep in zip(chain_slots(data,info['reloc_extern']),entry['external_files']):
            if target*4 >= manifest[dep]['size']:
                raise ValueError(f'File {fid} external target exceeds dependency {dep}')
    pack=b'SSB3DPAK'+struct.pack('<II',1,len(entries))+b''.join(entries)+b''.join(data_blobs)
    (out/'reloc.pak').write_bytes(pack)
    (out/'baserom.us.z64').write_bytes(rom)
    report=dict(rom_sha1=EXPECTED,rom_sha256=hashlib.sha256(rom).hexdigest(),
                pack_sha256=hashlib.sha256(pack).hexdigest(),files=len(entries),
                pack_bytes=len(pack),save_sha256=hashlib.sha256(SAVE.read_bytes()).hexdigest() if SAVE else None,
                extractor_sha256=hashlib.sha256(EXTRACTOR.read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps({'summary':report,'entries':manifest},indent=2))
    if not (out/'initial-save.bin').exists():(out/'initial-save.bin').write_bytes(bytes(32768))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()

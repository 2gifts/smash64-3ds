"""Find checksum-verified Smash backup records and convert their integer byte order."""
import argparse
import ctypes as C
import hashlib
import json
import struct
from build import ROOT
class VS(C.LittleEndianStructure):
    _fields_=[('ko_count',C.c_uint16*12),('time_used',C.c_uint32),('damage_given',C.c_uint32),('damage_taken',C.c_uint32),('unk',C.c_uint16),('selfdestructs',C.c_uint16),('games_played',C.c_uint16),('player_count_tally',C.c_uint16),('player_count_tallies',C.c_uint16*12),('played_against',C.c_uint16*12)]
class Single(C.LittleEndianStructure):
    _fields_=[('spgame_hiscore',C.c_uint32),('spgame_continues',C.c_uint32),('spgame_total_bonuses',C.c_uint32),('spgame_best_difficulty',C.c_uint8),('bonus1_time',C.c_uint32),('bonus1_task_count',C.c_uint8),('bonus2_time',C.c_uint32),('bonus2_task_count',C.c_uint8),('is_spgame_complete',C.c_uint8)]
class Backup(C.LittleEndianStructure):
    _fields_=[('vs_records',VS*12),('is_allow_screenflash',C.c_uint8),('sound_mono_or_stereo',C.c_uint8),('screen_adjust_h',C.c_int16),('screen_adjust_v',C.c_int16),('characters_fkind',C.c_uint8),('unlock_mask',C.c_uint8),('fighter_mask',C.c_uint16),('spgame_difficulty',C.c_uint8),('spgame_stock_count',C.c_uint8),('spgame_records',Single*12),('ground_mask',C.c_uint16),('vs_itemswitch_battles',C.c_uint8),('vs_total_battles',C.c_uint16),('error_flags',C.c_uint8),('boot',C.c_uint8),('signature',C.c_uint16),('checksum',C.c_int32)]
SIZE=C.sizeof(Backup)
assert (C.sizeof(VS),C.sizeof(Single),SIZE,Backup.signature.offset,Backup.checksum.offset)==(92,32,1516,1508,1512)
def checksum(data):return sum((i+1)*x for i,x in enumerate(data[:SIZE-4]))&0xffffffff
def swap_fields(data,kind,base=0):
    if issubclass(kind,C.Array):
        for i in range(kind._length_):swap_fields(data,kind._type_,base+i*C.sizeof(kind._type_))
    elif issubclass(kind,C.Structure):
        for name,field in kind._fields_:swap_fields(data,field,base+getattr(kind,name).offset)
    elif C.sizeof(kind)>1:data[base:base+C.sizeof(kind)]=data[base:base+C.sizeof(kind)][::-1]
def find_records(raw):
    found=[]
    for width in [1,2,4]:
        data=raw if width==1 else b''.join(raw[i:i+width][::-1] for i in range(0,len(raw),width))
        pos=0
        while True:
            sig=data.find(b'\x02\x9a',pos)
            if sig<0:break
            pos=sig+2;start=sig-Backup.signature.offset
            if start<0 or start+SIZE>len(data):continue
            record=data[start:start+SIZE]
            if checksum(record)==int.from_bytes(record[-4:],'big'):
                found.append((width,start,record))
    return found
def main():
    ap=argparse.ArgumentParser();ap.add_argument('save',type=str);args=ap.parse_args()
    from pathlib import Path
    raw=Path(args.save).read_bytes();found=find_records(raw)
    if not found:raise ValueError('No record has both a valid signature and weighted checksum; original left untouched')
    width,offset,record=found[0]
    native=bytearray(record);swap_fields(native,Backup);struct.pack_into('<I',native,SIZE-4,checksum(native))
    backup=Backup.from_buffer_copy(native)
    assert backup.signature==666 and (backup.checksum&0xffffffff)==checksum(native)
    restored=bytearray(native);swap_fields(restored,Backup)
    # Recompute the checksum because its byte ordering is part of the format, not source content.
    restored[-4:]=checksum(restored).to_bytes(4,'big')
    assert restored==record
    sram=bytearray(32768);sram[:SIZE]=native;second=(SIZE+15)&~15;sram[second:second+SIZE]=native
    destination=ROOT/'assets/initial-save.bin';destination.write_bytes(sram)
    report={'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),'record_bytes':SIZE,'verified_records':[{'word_bytes':w,'offset':o,'sha256':hashlib.sha256(r).hexdigest()} for w,o,r in found],'selected_offset':offset,'selected_word_bytes':width,'fighter_mask':hex(backup.fighter_mask),'unlock_mask':hex(backup.unlock_mask),'ground_mask':hex(backup.ground_mask),'completed_single_player':[i for i,r in enumerate(backup.spgame_records) if r.is_spgame_complete],'vs_total_battles':backup.vs_total_battles,'roundtrip_exact':True,'output_sha256':hashlib.sha256(sram).hexdigest()}
    (ROOT/'assets/save-import.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()

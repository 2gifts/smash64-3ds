"""Decode original UI sprites from the user's checked asset pack, once at build.
Only the private RomFS contains the pixels; source releases contain this recipe.
"""
import hashlib,importlib.util,json,re,struct,sys
from PIL import Image,ImageDraw
from build import ROOT,UPSTREAM,OUT

def main():
    path=UPSTREAM/'debug_tools/sprite_deswizzle/sprite_deswizzle.py'
    sys.path.insert(0,str(path.parent.parent/'reloc_extract'))
    spec=importlib.util.spec_from_file_location('sprite_reader',path);sp=importlib.util.module_from_spec(spec);spec.loader.exec_module(sp)
    defs=dict((n,int(v,16)) for n,v in re.findall(r'#define (\w+) \(\(intptr_t\)(0x[0-9a-fA-F]+)\)',(UPSTREAM/'include/reloc_data.us.h').read_text()))
    pack=(ROOT/'assets/reloc.pak').read_bytes()
    def sprite(file,name):
        fid=defs[file];off,size,deps,intern,extern,_=struct.unpack_from('<IIIHHI',pack,16+fid*20)
        data=pack[off:off+size];slots=sp.walk_reloc_chain(data,intern)
        s=sp.Sprite(data,defs[name],slots);bm=[sp.Bitmap(data,s.bitmap_off+i*16,slots) for i in range(s.nbitmaps)]
        rows=[]
        for b in bm:
            n=(b.width_img*b.actualHeight*s.bpp()+7)//8
            raw=data[b.buf_off:b.buf_off+n]
            # SP_TEXSHUF (0x200) marks the N64 sprite row permutation.
            if s.attr&0x200:raw=sp.apply_swizzle(raw,b.width_img,b.actualHeight,s.bpp(),'xor8' if s.bpp()==32 else 'port_current')
            if s.bmfmt==2:
                assert s.lut_off is not None
                palette=sp.decode_rgba16(data[s.lut_off:s.lut_off+s.nTLUT*2],s.nTLUT,1)
                indices=list(raw) if s.bpp()==8 else [q for v in raw for q in (v>>4,v&15)]
                pixels=[palette[i+b.LUToffset] for i in indices[:b.width_img*b.actualHeight]]
            else:pixels=sp.decode(raw,b.width_img,b.actualHeight,s.bmfmt,s.bmsiz)
            image=Image.new('RGBA',(b.width_img,b.actualHeight));image.putdata(pixels)
            rows.append(image)
        im=Image.new('RGBA',(s.width,s.height));y=0
        for row in rows:im.paste(row.crop((0,0,s.width,row.height)),(0,y));y+=row.height
        return im
    entries=[]
    def add(id,file,sym):entries.append((id,sprite('ll'+file+'FileID','ll'+file+sym)))
    for name in ['Mario','Fox','Donkey','Samus','Luigi','Link','Yoshi','Captain','Kirby','Pikachu','Purin','Ness']:
        add('PORTRAIT_'+name.upper(),'MNPlayersPortraits',name+'Sprite')
    for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':add('FONT_'+ch,'MNCommonFonts','Letter'+ch+'Sprite')
    for n in range(10):add('FONT_'+str(n),'MNCommon','Digit'+str(n)+'Sprite')
    for name in ['Apostrophe','Percent','Period']:add('FONT_'+name.upper(),'MNCommonFonts','Symbol'+name+'Sprite')
    for n in range(10):add('DAMAGE_'+str(n),'IFCommonPlayerDamage','Digit'+str(n)+'Sprite')
    add('DAMAGE_PERCENT','IFCommonPlayerDamage','SymbolPercentSprite')
    add('STONE','MNSelectCommon','StoneBackgroundSprite')
    add('LOGO','MNMain','SmashLogoSprite')
    for name in ['MarioModel','FoxModel','DkIcon','SamusModel','LuigiModel','LinkModel','YoshiModel','CaptainModel','KirbyModel','PikachuModel','PurinModel','NessModel']:
        add('STOCK_'+name.upper(),name,'StockSprite')
    dst=OUT/'bottom-art';dst.mkdir(exist_ok=True)
    descriptors=[];pixels=bytearray();start=8+len(entries)*12
    for i,(name,im) in enumerate(entries):
        descriptors.append(struct.pack('<III',im.width,im.height,start+len(pixels)))
        for r,g,b,a in im.get_flattened_data():pixels+=struct.pack('<HBB',((r>>3)<<11)|((g>>2)<<5)|(b>>3),(a*32+127)//255,0)
        im.save(dst/(name+'.png'))
    raw=b'BUI1'+struct.pack('<I',len(entries))+b''.join(descriptors)+pixels
    (ROOT/'assets/bottom-ui.bin').write_bytes(raw)
    header='#pragma once\n/* Indices only; extracted artwork remains in private RomFS. */\nenum {\n'+''.join('    BART_'+n+' = '+str(i)+',\n' for i,(n,_) in enumerate(entries))+'    BART_COUNT = '+str(len(entries))+'\n};\n'
    (ROOT/'include/bottom_art_ids.h').write_text(header)
    sheet=Image.new('RGB',(384,320),(32,31,28));draw=ImageDraw.Draw(sheet)
    for i,(name,im) in enumerate(entries):
        x=i%8*48;y=i//8*38
        thumb=im.copy();thumb.thumbnail((44,28));sheet.paste(thumb,(x,y),thumb);draw.text((x,y+28),name.replace('PORTRAIT_','')[:7],fill='white')
    sheet.save(dst/'sheet.png')
    (dst/'manifest.json').write_text(json.dumps(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),sprites=[dict(id=i,name=n,size=im.size) for i,(n,im) in enumerate(entries)]),indent=2))
    print('Decoded',len(entries),'original sprites;',len(raw),'bytes')

if __name__=='__main__':main()

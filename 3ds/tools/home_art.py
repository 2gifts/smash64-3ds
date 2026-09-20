"""Prepare the original cartridge label and logo for the 3DS package."""
from PIL import Image,ImageOps,ImageFilter
from build import ROOT
def prepare(dst):
    source=ROOT/'art/home-menu'
    cartridge=Image.open(source/'cartridge.jpg').convert('RGB')
    # Isolate the printed label from the photographed gray cartridge shell.
    label=cartridge.crop((307,83,883,741))
    icon=ImageOps.fit(label,(48,48),Image.Resampling.LANCZOS,centering=(.5,.20))
    icon=icon.filter(ImageFilter.UnsharpMask(radius=.55,percent=110,threshold=3))
    icon.save(dst/'icon.png')
    # Original artwork, aspect preserved, on a quiet warm paper background.
    banner=Image.new('RGB',(256,128));px=banner.load()
    for y in range(128):
        for x in range(256):
            shade=int(12*((x-128)**2/16384+(y-64)**2/4096))
            px[x,y]=(max(0,238-shade),max(0,227-shade),max(0,203-shade))
    logo=Image.open(source/'logo.png').convert('RGBA')
    logo=logo.crop(logo.getbbox());logo.thumbnail((244,100),Image.Resampling.LANCZOS)
    banner.paste(logo,((256-logo.width)//2,(128-logo.height)//2),logo)
    banner.save(dst/'banner.png')
if __name__=='__main__':
    from build import OUT
    prepare(OUT/'package')

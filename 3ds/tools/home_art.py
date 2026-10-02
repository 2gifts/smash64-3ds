"""Prepare the HOME Menu icon and banner for the 3DS package.

Uses the original cartridge label and logo when tools/fetch_home_art.py could
fetch them, and generated artwork otherwise. The unlocked profile's icon
carries an "ALL" badge so the two titles are easy to tell apart."""
import hashlib
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageFilter
from build import ROOT
from fetch_home_art import ART
def available(name):
    path=ROOT/'art/home-menu'/name
    digest=next(d for n,_,d in ART if n==name)
    return path if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest else None
def font(size):
    for name in ('arialbd.ttf','DejaVuSans-Bold.ttf'):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()
def generated_icon():
    icon=Image.new('RGB',(48,48),(200,32,32));d=ImageDraw.Draw(icon)
    d.ellipse((6,6,41,41),outline=(255,255,255),width=4);d.line((24,4,24,44),fill=(255,255,255),width=4)
    d.line((4,26,44,26),fill=(200,32,32),width=5)
    return icon
def badge(icon):
    d=ImageDraw.Draw(icon)
    d.rounded_rectangle((20,34,47,47),radius=3,fill=(250,196,30),outline=(60,40,0))
    d.text((33.5,41),'ALL',fill=(40,24,0),font=font(10),anchor='mm')
    return icon
def prepare(dst,profile='fresh'):
    cartridge=available('cartridge.jpg')
    if cartridge:
        # Isolate the printed label from the photographed gray cartridge shell.
        label=Image.open(cartridge).convert('RGB').crop((307,83,883,741))
        icon=ImageOps.fit(label,(48,48),Image.Resampling.LANCZOS,centering=(.5,.20))
        icon=icon.filter(ImageFilter.UnsharpMask(radius=.55,percent=110,threshold=3))
    else:icon=generated_icon()
    if profile=='unlocked':icon=badge(icon)
    icon.save(dst/'icon.png')
    # Original artwork, aspect preserved, on a quiet warm paper background.
    banner=Image.new('RGB',(256,128));px=banner.load()
    for y in range(128):
        for x in range(256):
            shade=int(12*((x-128)**2/16384+(y-64)**2/4096))
            px[x,y]=(max(0,238-shade),max(0,227-shade),max(0,203-shade))
    logo_path=available('logo.png')
    if logo_path:
        logo=Image.open(logo_path).convert('RGBA')
        logo=logo.crop(logo.getbbox());logo.thumbnail((244,100),Image.Resampling.LANCZOS)
        banner.paste(logo,((256-logo.width)//2,(128-logo.height)//2),logo)
    else:
        ImageDraw.Draw(banner).text((128,64),'SMASH 64',fill=(160,24,24),font=font(36),anchor='mm')
    if profile=='unlocked':
        ImageDraw.Draw(banner).text((128,118),'ALL UNLOCKED',fill=(120,80,0),font=font(12),anchor='mm')
    banner.save(dst/'banner.png')
if __name__=='__main__':
    from build import OUT
    prepare(OUT/'package')

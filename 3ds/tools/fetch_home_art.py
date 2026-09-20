"""Fetch the original artwork used by this private HOME Menu package."""
from urllib.request import Request,urlopen
from build import ROOT
def main():
    dst=ROOT/'art/home-menu';dst.mkdir(parents=True,exist_ok=True)
    for name,url in [
        ('cartridge.jpg','https://mario.wiki.gallery/images/0/09/SMBNACartridge.jpg'),
        ('logo.png','https://mario.wiki.gallery/images/f/fd/SuperSmashBros-Logo.png')]:
        (dst/name).write_bytes(urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read())
if __name__=='__main__':main()

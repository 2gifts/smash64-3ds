"""Fetch the original artwork used by the local HOME Menu package.

Pinned by hash. If the download fails or changes, the package uses generated
artwork instead (tools/home_art.py), so the build never depends on it."""
import hashlib
from urllib.request import Request,urlopen
from build import ROOT
ART=[('cartridge.jpg','https://mario.wiki.gallery/images/0/09/SMBNACartridge.jpg','07a30fd0af97aa40bbee0358d9bf137be4533d83487f0224d8c8908dc4cab174'),
     ('logo.png','https://mario.wiki.gallery/images/f/fd/SuperSmashBros-Logo.png','01a8a12aa822009fea4baaf8c3a28fc38fcd73dff75b31024448b2c0ebf88893')]
def main():
    dst=ROOT/'art/home-menu';dst.mkdir(parents=True,exist_ok=True)
    for name,url,digest in ART:
        path=dst/name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:continue
        try:
            data=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
        except OSError as error:
            print(f'HOME Menu artwork {name} unavailable ({error}); using generated artwork');continue
        if hashlib.sha256(data).hexdigest()!=digest:
            print(f'HOME Menu artwork {name} changed upstream; using generated artwork');continue
        path.write_bytes(data)
if __name__=='__main__':main()

"""Split a tall full-page screenshot into viewport-sized tiles you can Read.
  python3 scripts/qa_tiles.py qa_out/page_1440.png qa_out/tile [tile_height]"""
import sys
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
im=Image.open(sys.argv[1]); th=int(sys.argv[3]) if len(sys.argv)>3 else 1100
W,H=im.size; n=0
for y in range(0,H,th):
    t=im.crop((0,y,W,min(H,y+th)))
    if t.size[0]>1400: t=t.resize((1400,int(t.size[1]*1400/t.size[0])))
    t.save(f"{sys.argv[2]}_{n:02d}.png"); n+=1
print(n,"tiles")

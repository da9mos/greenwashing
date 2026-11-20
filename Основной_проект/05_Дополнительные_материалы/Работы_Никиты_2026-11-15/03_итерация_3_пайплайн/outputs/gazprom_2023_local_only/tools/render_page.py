import argparse
from pathlib import Path
import pymupdf
ap=argparse.ArgumentParser();ap.add_argument('pdf');ap.add_argument('page',type=int);ap.add_argument('png');ap.add_argument('--scale',type=float,default=2);a=ap.parse_args();d=pymupdf.open(a.pdf)
if not 1<=a.page<=len(d):raise SystemExit('Page must be 1..N')
Path(a.png).parent.mkdir(parents=True,exist_ok=True);d[a.page-1].get_pixmap(matrix=pymupdf.Matrix(a.scale,a.scale)).save(a.png)

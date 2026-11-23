"""Banc synthétique Linux. Fichiers temporaires et un sous-processus neuf par mesure."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


def prepare(root, depth, large=False):
    # Grille int16. Les motifs se répètent dans z volontairement.
    m = {"profil":"FLUX-CANON-R02","A":[],"B":[]}
    width = 1000 if large else 512
    entries = [("A","X",1),("A","Y",3),("B","U",1),("B","V",2)]
    if large:
        entries.extend((group, "extra"+str(i), 4+i+8*j)
                       for j,group in enumerate(("A","B")) for i in range(8))
    for group, ident, value in entries:
        folder=root/"lots"/group
        folder.mkdir(parents=True,exist_ok=True)
        h=bytearray(352)
        struct.pack_into("<i",h,0,348)
        struct.pack_into("<8h",h,40,3,width,width,depth,1,1,1,1)
        struct.pack_into("<hh",h,70,4,16)
        struct.pack_into("<8f",h,76,*([1.0]*8))
        struct.pack_into("<fff",h,108,352.,1.,0.)
        h[344:348]=b"n+1\0"
        slab=struct.pack("<h",value)*(width*width)
        digest=hashlib.sha256(h)
        with (folder/(ident+".nii")).open("xb") as f:
            f.write(h)
            for _ in range(depth):
                digest.update(slab)
                f.write(slab)
        m[group].append({"id":ident,"taille":352+len(slab)*depth,"sha256":digest.hexdigest()})
    raw=json.dumps(m).encode()
    (root/"manifeste.json").write_bytes(raw)
    (root/"rapport.json").write_text(json.dumps({"profil":m["profil"],
        "manifeste_sha256":hashlib.sha256(raw).hexdigest(),"paires":[["X","U"]]}),encoding="utf8")


def measure(root):
    import resource
    import time
    from verifier_flux import verify
    start=time.monotonic()
    code,result=verify(root/"manifeste.json",root/"rapport.json")
    result.update(duree_s=round(time.monotonic()-start,3),
                  pic_RSS_processus_Mio=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
                  octets_nii=sum(p.stat().st_size for p in root.glob("lots/*/*.nii")))
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesurer",type=Path)
    parser.add_argument("--profondeurs",nargs="+",type=int,default=[32,512])
    parser.add_argument("--pres-de-20go",action="store_true",help="20 fichiers, 19,96 Go écrits en entier")
    parser.add_argument("--espace",type=Path,help="dossier temporaire sur disque local")
    a=parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("ce banc mesure le RSS sous Linux")
    if a.mesurer:
        raise SystemExit(measure(a.mesurer))
    if a.pres_de_20go:
        if a.espace is None or shutil.disk_usage(a.espace).free < 21_000_000_000:
            parser.error("le banc de 19,96 Go demande --espace avec au moins 21 Go disponibles")
    for depth in ([499] if a.pres_de_20go else a.profondeurs):
        if not 1 <= depth <= 4095:
            parser.error("profondeur admise de 1 à 4095")
        with tempfile.TemporaryDirectory(dir=a.espace) as d:
            prepare(Path(d),depth,a.pres_de_20go)
            subprocess.run([sys.executable,"-B",__file__,"--mesurer",d],check=True)

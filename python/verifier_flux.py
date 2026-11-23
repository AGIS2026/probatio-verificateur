"""R02 de développement. Vérification exacte inter-lots NIfTI-1 par blocs."""
from __future__ import annotations
import argparse
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
import hashlib
from itertools import zip_longest
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

import numpy as np

PROFILE = "FLUX-CANON-R02"
METHOD = b"PROBATIO-NIFTI-CANON-R01"
TYPES = {2: "u1", 256: "i1", 4: "i2", 512: "u2", 8: "i4", 768: "u4", 16: "f4", 64: "f8"}
CHUNK_VOXELS = 131072
MAX_FILE = 2**31
MAX_TOTAL = 20_000_000_000
ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class Invalid(ValueError):
    pass


def check(condition, reason):
    if not condition:
        raise Invalid(reason)


def object_unique(items):
    obj = {}
    for key, value in items:
        check(key not in obj, "champ JSON répété")
        obj[key] = value
    return obj


def document(path, limit):
    with path.open("rb") as f:
        data = f.read(limit + 1)
    check(len(data) <= limit, "document trop grand")
    return json.loads(data.decode("utf8"), object_pairs_hook=object_unique), hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Entry:
    ident: str
    path: Path
    size: int
    sha: str


def source_path(root, rel):
    check(root.is_dir() and not root.is_symlink(), "racine illisible ou symbolique")
    check(isinstance(rel,str) and rel.endswith(".nii") and not any(c in rel for c in "\\:\x00"), "chemin NIfTI invalide")
    parts = rel.split("/")
    check(all(p not in ("", ".", "..") for p in parts), "chemin non relatif")
    path = root
    for part in parts:
        path = path / part
        check(not path.is_symlink(), "lien symbolique dans le lot")
    return path


def load_manifest(path, root=None):
    m, sha = document(path, 4 * 1024**2)
    check(isinstance(m, dict) and set(m) == {"profil","A","B"} and m["profil"] == PROFILE, "manifeste invalide")
    root = Path(root) if root is not None else path.parent / "lots"
    check(root.is_dir() and not root.is_symlink(), "racine illisible ou symbolique")
    used = set()
    groups = {}
    for g in ("A","B"):
        entries = {}
        check(isinstance(m[g], list) and 1 <= len(m[g]) <= 1000, "taille des lots hors périmètre")
        for row in m[g]:
            check(isinstance(row, dict) and set(row) in ({"id","taille","sha256"},{"id","taille","sha256","chemin"}), "ligne du manifeste invalide")
            i, size, raw = row["id"], row["taille"], row["sha256"]
            check(isinstance(i,str) and ID.fullmatch(i) and i not in entries, "identifiant invalide ou répété")
            check(type(size) is int and 352 <= size <= MAX_FILE, "taille du fichier hors limites")
            check(isinstance(raw,str) and re.fullmatch("[a-f0-9]{64}",raw), "SHA-256 invalide")
            rel = row.get("chemin", f"{g}/{i}.nii")
            source = source_path(root, rel)
            check(source not in used, "un chemin est déclaré plusieurs fois")
            used.add(source)
            entries[i] = Entry(i, source, size, raw)
        groups[g] = entries
    check(len(used) <= 1000 and sum(e.size for group in groups.values() for e in group.values()) <= MAX_TOTAL, "lot hors limites")
    return sha, groups


def snapshot(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def same_snapshot(e, stamp):
    st = e.path.lstat()
    check(stat.S_ISREG(st.st_mode) and snapshot(st) == stamp, "source modifiée pendant le contrôle")


def canonical_blocks(e, stamp, block=CHUNK_VOXELS):
    """Toujours épuiser le générateur pour valider le SHA brut et la stabilité."""
    check(block > 0, "bloc invalide")
    same_snapshot(e, stamp)
    with e.path.open("rb") as f:
        check(snapshot(os.fstat(f.fileno())) == stamp and stamp[2] == e.size, "source différente du manifeste")
        raw = hashlib.sha256()

        def take(n):
            b = f.read(n)
            check(len(b) == n, "fichier tronqué")
            raw.update(b)
            return b

        h = take(352)
        order = {struct.pack("<i",348): "<", struct.pack(">i",348): ">"}.get(h[:4])
        check(order and h[344:348] == b"n+1\0", "format hors périmètre")
        dim = struct.unpack_from(order+"8h", h, 40)
        shape = dim[1:4]
        check(dim[0] == 3 and all(1 <= x <= 4096 for x in shape), "dimensions hors périmètre")
        dt, bits = struct.unpack_from(order+"hh", h, 70)
        check(dt in TYPES, "type voxel hors périmètre")
        dtype = np.dtype(order+TYPES[dt])
        check(dtype.itemsize*8 == bits, "bitpix incohérent")
        offset, slope, intercept = struct.unpack_from(order+"fff",h,108)
        check(offset.is_integer() and 352 <= offset <= 2**24, "offset invalide")
        skip = int(offset)-352
        while skip:
            n = min(skip, 1024*1024)
            take(n)
            skip -= n
        if slope == 0:
            slope, intercept = 1.0, 0.0
        check(math.isfinite(slope) and math.isfinite(intercept), "échelle non finie")
        remaining = math.prod(shape)
        tail = e.size - int(offset) - remaining * dtype.itemsize
        check(0 <= tail <= 4096, "taille incohérente ou octets finaux hors limites")
        desc = {"forme_xyz":shape,"ordre":"x_plus_rapide","valeurs":"f64le","zero":"positif"}
        yield METHOD+b"\0"+json.dumps(desc,sort_keys=True,separators=(",",":")).encode("ascii")+b"\0"
        while remaining:
            n = min(block, remaining)
            buf = take(n*dtype.itemsize)
            v = np.frombuffer(buf, dtype=dtype).astype("<f8",copy=True)
            with np.errstate(over="ignore", invalid="ignore", under="ignore"):
                np.multiply(v, slope, out=v)
                np.add(v, intercept, out=v)
            check(np.isfinite(v).all(), "valeurs décodées non finies")
            v[v == 0] = 0
            yield v.tobytes()
            remaining -= n
        take(tail)
        check(not f.read(1) and raw.hexdigest() == e.sha, "empreinte source divergente")
        check(snapshot(os.fstat(f.fileno())) == stamp, "source modifiée pendant la lecture")
    same_snapshot(e, stamp)


def compare(a, b, stamps, block):
    equal = True
    with closing(canonical_blocks(a, stamps[a], block)) as left, closing(canonical_blocks(b, stamps[b], block)) as right:
        for x, y in zip_longest(left, right):
            if x != y:
                equal = False
    return equal


def scan(groups, block=CHUNK_VOXELS, key_of_hash=lambda h: h, between_passes=None):
    index = {"A": defaultdict(list), "B": defaultdict(list)}
    stamps, hashes = {}, {}
    for g, entries in groups.items():
        for e in entries.values():
            stamps[e] = snapshot(e.path.lstat())
            digest = hashlib.sha256()
            for part in canonical_blocks(e, stamps[e], block):
                digest.update(part)
            hashes[e] = digest.hexdigest()
            index[g][key_of_hash(hashes[e])].append(e)
    if between_passes is not None:
        between_passes()
    pairs = set()
    comparisons = 0
    for k in index["A"].keys() & index["B"].keys():
        # Une classe possède un représentant réellement comparé et deux listes d'identifiants.
        classes = []
        for g in ("A","B"):
            for e in index[g][k]:
                for representative, members in classes:
                    comparisons += 1
                    if compare(e, representative, stamps, block):
                        break
                else:
                    members = {"A": [], "B": []}
                    classes.append((e, members))
                members[g].append(e.ident)
        for _, members in classes:
            pairs.update((a,b) for a in members["A"] for b in members["B"])
    for e, stamp in stamps.items():
        same_snapshot(e, stamp)
    return pairs, hashes, comparisons


def report_pairs(r, manifest_sha):
    check(isinstance(r,dict) and set(r)=={"profil","manifeste_sha256","paires"}
          and r["profil"] == PROFILE and r["manifeste_sha256"] == manifest_sha, "mauvais profil ou manifeste")
    rows = r["paires"]
    check(isinstance(rows,list), "liste de paires attendue")
    pairs = set()
    for row in rows:
        check(isinstance(row,list) and len(row)==2 and all(isinstance(i,str) and ID.fullmatch(i) for i in row), "paire invalide")
        pair = tuple(row)
        check(pair not in pairs, "paire répétée")
        pairs.add(pair)
    return pairs


def verify(manifest, report, root=None):
    try:
        sha, groups = load_manifest(manifest, root)
        expected, _, count = scan(groups)
    except (ValueError,OSError,RecursionError) as e:
        return 2, {"statut":"CONTROLE_INCOMPLET", "motif":str(e) if isinstance(e,Invalid) else "lecture impossible"}
    try:
        r, _ = document(report, 64 * 1024**2)
        seen = report_pairs(r, sha)
    except (ValueError,OSError,RecursionError) as e:
        return 1, {"statut":"RAPPORT_REJETE", "motif":str(e) if isinstance(e,Invalid) else "rapport illisible"}
    missing, extra = len(expected-seen), len(seen-expected)
    ok = not missing and not extra
    return int(not ok), {"statut":"RAPPORT_ACCEPTE" if ok else "RAPPORT_REJETE",
            "A":len(groups["A"]),"B":len(groups["B"]),"paires_exactes":len(expected),
            "comparaisons_integrales":count, "manquantes":missing, "en_trop":extra}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifeste", type=Path)
    p.add_argument("rapport", type=Path)
    p.add_argument("--racine",type=Path,help="Racine des chemins du manifeste, par défaut lots/ à côté du manifeste")
    args = p.parse_args()
    code, result = verify(args.manifeste, args.rapport, args.racine)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(code)

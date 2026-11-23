"""Régressions du prototype flux. Aucun accès réseau, données synthétiques."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from verifier_flux import Entry, Invalid, canonical_blocks, load_manifest, scan, snapshot, verify

HERE=Path(__file__).resolve().parent


class Flux(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)/"ex"
        shutil.copytree(HERE/"exemple", self.root)
        self.man=self.root/"manifeste.json"
        self.sha,self.g=load_manifest(self.man)
        self.truth={("S0000","B01"),("S0000","B02")}

    def test_rapports_livres(self):
        for nom,code in [("exact",0),("omission",1),("ajout",1)]:
            with self.subTest(nom=nom):
                self.assertEqual(verify(self.man,self.root/"rapports"/(nom+".json"))[0],code)

    def test_frontieres_bloc(self):
        for n in (1,3,8,19):
            self.assertEqual(scan(self.g,n)[0],self.truth)

    def test_collision_totale(self):
        self.assertEqual(scan(self.g,2,lambda h: 0)[0],self.truth)

    def test_rattachement_manifeste(self):
        self.man.write_bytes(self.man.read_bytes()+b" ")
        self.assertEqual(verify(self.man,self.root/"rapports/exact.json")[0],1)

    def test_paires_illegitimes(self):
        r=json.loads((self.root/"rapports/exact.json").read_bytes())
        for pair in (["S0000","B01"],["absent","B01"]):
            doc=dict(r,paires=r["paires"]+[pair])
            f=self.root/"bad.json"; f.write_text(json.dumps(doc))
            self.assertEqual(verify(self.man,f)[0],1)

    def test_vrai_zero(self):
        self.g["B"]={"B03":self.g["B"]["B03"]}
        self.assertEqual(scan(self.g)[0],set())

    def test_faux_zero(self):
        doc=json.loads((self.root/"rapports/exact.json").read_bytes());doc["paires"]=[]
        f=self.root/"zero.json"; f.write_text(json.dumps(doc))
        self.assertEqual(verify(self.man,f)[0],1)

    def test_entree_absente(self):
        self.g["A"]["S0000"].path.unlink()
        code,r=verify(self.man,self.root/"rapports/exact.json")
        self.assertEqual(code,2);self.assertNotIn("paires_exactes",r)

    def test_entree_alteree_meme_taille(self):
        p=self.g["B"]["B03"].path
        raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        self.assertEqual(verify(self.man,self.root/"rapports/exact.json")[0],2)

    def test_changement_entre_passes(self):
        for i in ("B01","B03"):
            e=self.g["B"][i]
            with self.assertRaises(Invalid):
                scan(self.g,between_passes=lambda: e.path.write_bytes(e.path.read_bytes()+b"x"))
            e.path.write_bytes(e.path.read_bytes()[:-1])

    def test_manifeste_ambigu(self):
        m=json.loads(self.man.read_bytes());m["A"].append(m["A"][0]); self.man.write_text(json.dumps(m))
        self.assertEqual(verify(self.man,self.root/"rapports/exact.json")[0],2)

    def test_chemin_hors_racine(self):
        m=json.loads(self.man.read_bytes());m["A"][0]["chemin"]="../S0000.nii";self.man.write_text(json.dumps(m))
        self.assertEqual(verify(self.man,self.root/"rapports/exact.json")[0],2)

    def test_plusieurs_representants(self):
        # Dans le même seau, 2 A et 2 B égaux, et des faux candidats de même taille.
        p=self.g["A"]["S0000"]
        self.g["A"]["X"]=Entry("X",p.path,p.size,p.sha)
        pairs,_,_=scan(self.g,key_of_hash=lambda h:0)
        self.assertEqual(pairs,self.truth|{("X","B01"),("X","B02")})

    def test_huit_types_deux_boutismes(self):
        for code,fmt in [(2,"B"),(256,"b"),(4,"h"),(512,"H"),(8,"i"),(768,"I"),(16,"f"),(64,"d")]:
            for order in "<>":
                with self.subTest(code=code,order=order):
                    payload=struct.pack(order+"4"+fmt,0,1,2,3)
                    h=bytearray(368)
                    struct.pack_into(order+"i",h,0,348)
                    struct.pack_into(order+"8h",h,40,3,2,2,1,0,0,0,0)
                    struct.pack_into(order+"hh",h,70,code,struct.calcsize(fmt)*8)
                    struct.pack_into(order+"fff",h,108,368,2,-1)
                    h[344:348]=b"n+1\0"
                    raw=h+payload+b"x";p=self.root/"t.nii";p.write_bytes(raw)
                    e=Entry("T",p,len(raw),hashlib.sha256(raw).hexdigest())
                    comp=list(canonical_blocks(e,snapshot(p.stat()),3))
                    self.assertEqual(b"".join(comp[1:]),struct.pack("<4d",-1,1,3,5))

    def test_zero_signe_donnees_non_finies_et_debordement(self):
        p=self.root/"temp.nii";h=bytearray(self.g["A"]["S0000"].path.read_bytes()[:352])
        struct.pack_into("<hh",h,70,64,64)
        def decode(values,slope,intercept):
            struct.pack_into("<ff",h,112,slope,intercept)
            data=h+struct.pack("<8d",*values);p.write_bytes(data)
            e=Entry("t",p,len(data),hashlib.sha256(data).hexdigest())
            return b"".join(list(canonical_blocks(e,snapshot(p.stat()),3))[1:])
        self.assertEqual(decode([-0.0]*8,0,float("nan")),bytes(64))
        for val,slope in [(float("nan"),1.),(float("inf"),1.),(1e308,32.)]:
            with self.assertRaises(Invalid):
                decode([val]*8,slope,0)


if __name__=="__main__":
    unittest.main()

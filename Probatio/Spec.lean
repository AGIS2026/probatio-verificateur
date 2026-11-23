/-!
# PROBATIO · Spécification

Recherche des volumes identiques entre deux lots (par exemple entraînement et test),
sur des volumes déjà décodés en mots binary64 canoniques.

Ce fichier ne contient que des définitions : ce qu'est un rapport exact,
et le contrat qu'un vérificateur doit remplir. Les démonstrations sont dans
`Probatio/Verificateur.lean`.
-/

namespace Probatio

abbrev IdVol := String
abbrev Paire := IdVol × IdVol
abbrev Rapport := List Paire

/-- Volume canonique : forme XYZ et valeurs décodées (binary64, x le plus rapide). -/
structure Volume where
  nx : Nat
  ny : Nat
  nz : Nat
  valeurs : List UInt64
  deriving DecidableEq

structure Entree where
  id : IdVol
  volume : Volume
  deriving DecidableEq

abbrev Lot := List Entree

/-- Éléments deux à deux distincts (définition locale, indépendante de la version de Lean). -/
def Distincts {α : Type} : List α → Prop
  | [] => True
  | x :: l => x ∉ l ∧ Distincts l

/-- Mot binary64 fini et différent de -0. -/
def MotAdmis (v : UInt64) : Prop :=
  (v.toNat / 2 ^ 52) % 2048 < 2047 ∧ v.toNat ≠ 2 ^ 63

def VolumeAdmis (v : Volume) : Prop :=
  0 < v.nx ∧ 0 < v.ny ∧ 0 < v.nz ∧
  v.valeurs.length = v.nx * v.ny * v.nz ∧
  ∀ w ∈ v.valeurs, MotAdmis w

def LotAdmis (lot : Lot) : Prop :=
  lot ≠ [] ∧ Distincts (lot.map Entree.id) ∧ ∀ e ∈ lot, VolumeAdmis e.volume

/-- `p` est une paire attendue : une entrée de A et une entrée de B de même volume. -/
def Attendue (a b : Lot) (p : Paire) : Prop :=
  ∃ x ∈ a, ∃ y ∈ b, p = (x.id, y.id) ∧ x.volume = y.volume

/-- Un rapport exact cite chaque paire attendue une seule fois, et rien d'autre.
    La condition porte sur tout couple d'identifiants, y compris inconnus. -/
def RapportExact (a b : Lot) (r : Rapport) : Prop :=
  Distincts r ∧ ∀ p : Paire, p ∈ r ↔ Attendue a b p

/-- Contrat : le vérificateur accepte si et seulement si le rapport est exact.
    Le sens « si » exclut un vérificateur qui refuserait tout. -/
def Contrat (verif : Lot → Lot → Rapport → Bool) : Prop :=
  ∀ (a b : Lot), LotAdmis a → LotAdmis b →
    ∀ r : Rapport, (verif a b r = true ↔ RapportExact a b r)

/-- Le regroupement par clé (empreinte) ne doit rien changer, quelle que soit la clé,
    y compris une clé constante : aucune hypothèse d'absence de collision. -/
def ContratParCles (verif : (Volume → Nat) → Lot → Lot → Rapport → Bool) : Prop :=
  ∀ cle : Volume → Nat, Contrat (verif cle)

end Probatio

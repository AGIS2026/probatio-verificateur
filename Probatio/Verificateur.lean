import Probatio.Spec

/-!
# PROBATIO · Vérificateur exécutable et démonstration du contrat

* `verifier` : recalcule les paires attendues, puis compare au rapport.
* `verifierCle` : même chose avec un préfiltrage par clé (empreinte).
* `verifier_correct` : `Contrat verifier`.
* `verifierCle_correct` : `ContratParCles verifierCle`, pour toute clé, même constante.
-/

namespace Probatio

/-! ## Outils booléens et leurs lemmes -/

def appartient (p : Paire) : List Paire → Bool
  | [] => false
  | q :: l => decide (p = q) || appartient p l

theorem appartient_iff (p : Paire) (l : List Paire) :
    appartient p l = true ↔ p ∈ l := by
  induction l with
  | nil =>
    constructor
    · intro h
      simp [appartient] at h
    · intro h
      cases h
  | cons q l ih =>
    simp only [appartient, Bool.or_eq_true, decide_eq_true_eq, ih, List.mem_cons, iff_self]

def tous (f : Paire → Bool) : List Paire → Bool
  | [] => true
  | q :: l => f q && tous f l

theorem tous_iff (f : Paire → Bool) (l : List Paire) :
    tous f l = true ↔ ∀ p ∈ l, f p = true := by
  induction l with
  | nil =>
    constructor
    · intro _ p hp
      cases hp
    · intro _
      rfl
  | cons q l ih =>
    simp only [tous, Bool.and_eq_true, ih]
    constructor
    · rintro ⟨hq, hl⟩ p hp
      rcases List.mem_cons.mp hp with h | h
      · subst h
        exact hq
      · exact hl p h
    · intro h
      exact ⟨h q (List.mem_cons.mpr (Or.inl rfl)),
             fun p hp => h p (List.mem_cons.mpr (Or.inr hp))⟩

def sansRepetition : List Paire → Bool
  | [] => true
  | q :: l => !(appartient q l) && sansRepetition l

theorem sansRepetition_iff (l : List Paire) :
    sansRepetition l = true ↔ Distincts l := by
  induction l with
  | nil =>
    exact ⟨fun _ => trivial, fun _ => rfl⟩
  | cons q l ih =>
    simp only [sansRepetition, Distincts, Bool.and_eq_true, ih]
    constructor
    · rintro ⟨h1, h2⟩
      refine ⟨fun hq => ?_, h2⟩
      have h3 := (appartient_iff q l).mpr hq
      rw [h3] at h1
      simp at h1
    · rintro ⟨h1, h2⟩
      refine ⟨?_, h2⟩
      cases h : appartient q l with
      | false => rfl
      | true => exact absurd ((appartient_iff q l).mp h) h1

/-! ## Paires attendues -/

def correspondants (x : Entree) : Lot → List Paire
  | [] => []
  | y :: b =>
    if x.volume = y.volume then (x.id, y.id) :: correspondants x b
    else correspondants x b

theorem mem_correspondants (x : Entree) (b : Lot) (p : Paire) :
    p ∈ correspondants x b ↔ ∃ y ∈ b, p = (x.id, y.id) ∧ x.volume = y.volume := by
  induction b with
  | nil =>
    simp [correspondants]
  | cons y b ih =>
    constructor
    · intro hp
      by_cases h : x.volume = y.volume
      · simp only [correspondants] at hp
        rw [if_pos h] at hp
        rcases List.mem_cons.mp hp with hp | hp
        · exact ⟨y, List.mem_cons.mpr (Or.inl rfl), hp, h⟩
        · obtain ⟨z, hz, hpz, hv⟩ := ih.mp hp
          exact ⟨z, List.mem_cons.mpr (Or.inr hz), hpz, hv⟩
      · simp only [correspondants] at hp
        rw [if_neg h] at hp
        obtain ⟨z, hz, hpz, hv⟩ := ih.mp hp
        exact ⟨z, List.mem_cons.mpr (Or.inr hz), hpz, hv⟩
    · rintro ⟨z, hz, hpz, hv⟩
      rcases List.mem_cons.mp hz with hz | hz
      · subst hz
        simp only [correspondants]
        rw [if_pos hv]
        exact List.mem_cons.mpr (Or.inl hpz)
      · by_cases h : x.volume = y.volume
        · simp only [correspondants]
          rw [if_pos h]
          exact List.mem_cons.mpr (Or.inr (ih.mpr ⟨z, hz, hpz, hv⟩))
        · simp only [correspondants]
          rw [if_neg h]
          exact ih.mpr ⟨z, hz, hpz, hv⟩

def attendues : Lot → Lot → List Paire
  | [], _ => []
  | x :: a, b => correspondants x b ++ attendues a b

theorem mem_attendues (a b : Lot) (p : Paire) :
    p ∈ attendues a b ↔ Attendue a b p := by
  induction a with
  | nil =>
    simp [attendues, Attendue]
  | cons x a ih =>
    simp only [attendues, List.mem_append, mem_correspondants, ih, Attendue]
    constructor
    · rintro (⟨y, hy, hp, hv⟩ | ⟨x', hx', y, hy, hp, hv⟩)
      · exact ⟨x, List.mem_cons.mpr (Or.inl rfl), y, hy, hp, hv⟩
      · exact ⟨x', List.mem_cons.mpr (Or.inr hx'), y, hy, hp, hv⟩
    · rintro ⟨x', hx', y, hy, hp, hv⟩
      rcases List.mem_cons.mp hx' with h | h
      · subst h
        exact Or.inl ⟨y, hy, hp, hv⟩
      · exact Or.inr ⟨x', h, y, hy, hp, hv⟩

/-! ## Variante avec préfiltrage par clé

On ne compare intégralement que les volumes de même clé. Deux volumes égaux ont
forcément la même clé (`congrArg`), donc aucune paire n'est perdue, quelle que
soit la clé : la complétude ne repose sur aucune propriété cryptographique. -/

def correspondantsCle (cle : Volume → Nat) (x : Entree) : Lot → List Paire
  | [] => []
  | y :: b =>
    if cle x.volume = cle y.volume then
      (if x.volume = y.volume then (x.id, y.id) :: correspondantsCle cle x b
       else correspondantsCle cle x b)
    else correspondantsCle cle x b

theorem correspondantsCle_eq (cle : Volume → Nat) (x : Entree) (b : Lot) :
    correspondantsCle cle x b = correspondants x b := by
  induction b with
  | nil =>
    simp only [correspondantsCle, correspondants]
  | cons y b ih =>
    simp only [correspondantsCle, correspondants, ih]
    by_cases hv : x.volume = y.volume
    · rw [if_pos (congrArg cle hv), if_pos hv]
    · rw [if_neg hv, ite_self]

def attenduesCle (cle : Volume → Nat) : Lot → Lot → List Paire
  | [], _ => []
  | x :: a, b => correspondantsCle cle x b ++ attenduesCle cle a b

theorem attenduesCle_eq (cle : Volume → Nat) (a b : Lot) :
    attenduesCle cle a b = attendues a b := by
  induction a with
  | nil =>
    simp only [attenduesCle, attendues]
  | cons x a ih =>
    simp only [attenduesCle, attendues, correspondantsCle_eq, ih]

/-! ## Vérificateurs -/

def verifierAvec (att : List Paire) (r : Rapport) : Bool :=
  sansRepetition r && tous (fun p => appartient p att) r && tous (fun p => appartient p r) att

def verifier (a b : Lot) (r : Rapport) : Bool :=
  verifierAvec (attendues a b) r

def verifierCle (cle : Volume → Nat) (a b : Lot) (r : Rapport) : Bool :=
  verifierAvec (attenduesCle cle a b) r

theorem verifierAvec_iff (att r : List Paire) :
    verifierAvec att r = true ↔ Distincts r ∧ ∀ p : Paire, p ∈ r ↔ p ∈ att := by
  simp only [verifierAvec, Bool.and_eq_true, sansRepetition_iff, tous_iff, appartient_iff]
  constructor
  · rintro ⟨⟨hd, h1⟩, h2⟩
    exact ⟨hd, fun p => ⟨h1 p, h2 p⟩⟩
  · rintro ⟨hd, h⟩
    exact ⟨⟨hd, fun p hp => (h p).mp hp⟩, fun p hp => (h p).mpr hp⟩

theorem verifier_iff (a b : Lot) (r : Rapport) :
    verifier a b r = true ↔ RapportExact a b r := by
  unfold verifier RapportExact
  rw [verifierAvec_iff]
  constructor
  · rintro ⟨hd, h⟩
    exact ⟨hd, fun p => (h p).trans (mem_attendues a b p)⟩
  · rintro ⟨hd, h⟩
    exact ⟨hd, fun p => (h p).trans (mem_attendues a b p).symm⟩

/-! ## Théorèmes principaux

Les hypothèses `LotAdmis` du contrat ne sont pas utilisées : le résultat tient
pour tous les lots. -/

theorem verifier_correct : Contrat verifier := by
  unfold Contrat
  intro a b _ _ r
  exact verifier_iff a b r

theorem verifierCle_correct : ContratParCles verifierCle := by
  unfold ContratParCles Contrat
  intro cle a b _ _ r
  unfold verifierCle
  rw [attenduesCle_eq]
  exact verifier_iff a b r

end Probatio

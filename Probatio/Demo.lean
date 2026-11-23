import Probatio.Verificateur

/-!
# Démonstration exécutable (lots jouets)

S0000 a le même contenu que B01 et B02. B03 diffère d'une seule valeur.
A02 a les mêmes valeurs que S0000 sur une autre forme : ce n'est pas une paire.
Chaque exemple exige le verdict indiqué à la compilation.
-/

namespace Probatio.Demo
open Probatio

def cube (xs : List UInt64) : Volume := ⟨2, 2, 2, xs⟩

def lotA : Lot :=
  [⟨"S0000", cube [0, 1, 2, 3, 4, 5, 6, 7]⟩,
   ⟨"A02", ⟨1, 2, 4, [0, 1, 2, 3, 4, 5, 6, 7]⟩⟩]

def lotB : Lot :=
  [⟨"B01", cube [0, 1, 2, 3, 4, 5, 6, 7]⟩,
   ⟨"B02", cube [0, 1, 2, 3, 4, 5, 6, 7]⟩,
   ⟨"B03", cube [0, 1, 2, 3, 4, 5, 6, 8]⟩]

-- exact : true
example : verifier lotA lotB [("S0000", "B01"), ("S0000", "B02")] = true := by decide
-- omission : false
example : verifier lotA lotB [("S0000", "B01")] = false := by decide
-- ajout : false
example : verifier lotA lotB [("S0000", "B01"), ("S0000", "B02"), ("S0000", "B03")] = false := by decide
-- faux zéro : false
example : verifier lotA lotB [] = false := by decide
-- clé constante (collision totale), rapport exact : true
example : verifierCle (fun _ => 0) lotA lotB [("S0000", "B02"), ("S0000", "B01")] = true := by decide

end Probatio.Demo

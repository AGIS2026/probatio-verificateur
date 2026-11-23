"""Accepte uniquement deux inventaires Lean 4.15 complets avec axiomes standard."""
from pathlib import Path
import re
import sys

THEOREMES = {"Probatio.verifier_correct", "Probatio.verifierCle_correct"}
AXIOMES_STANDARD = {"propext", "Quot.sound", "Classical.choice"}
LIGNE = re.compile(
    r"\s*'([^']+)'\s+(?:does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])"
)


def controler(texte):
    position = 0
    vus = set()
    while texte[position:].strip():
        match = LIGNE.match(texte, position)
        if match is None:
            raise ValueError("sortie Lean inattendue ou incomplète")
        nom, liste = match.groups()
        if nom not in THEOREMES or nom in vus:
            raise ValueError(f"théorème inattendu ou répété : {nom}")
        vus.add(nom)
        axiomes = {x.strip() for x in liste.split(",")} if liste else set()
        hors_liste = axiomes - AXIOMES_STANDARD
        if hors_liste:
            raise ValueError("axiome à examiner : " + ", ".join(sorted(hors_liste)))
        position = match.end()
    if vus != THEOREMES:
        raise ValueError("inventaire manquant pour au moins un théorème")


if __name__ == "__main__":
    try:
        controler(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as erreur:
        raise SystemExit(str(erreur))

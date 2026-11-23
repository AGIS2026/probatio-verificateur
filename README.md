# PROBATIO · Vérificateur de correspondances exactes en Lean 4

**Statut de cette révision.** Deux démonstrations sont proposées pour Lean 4.15.0. Leur première compilation reste à établir. Le résultat des tests Python est distinct. Une fois la CI réussie, rattacher le résultat au commit et à son journal d’axiomes.

**English summary.** This project proposes two Lean 4 proofs about an exact-match report over decoded volumes. It includes a reference checker and a variant that filters candidates by any key, including a constant key. Kernel verification of this revision is pending.

## Énoncés à vérifier

Sur des volumes déjà décodés (forme XYZ et valeurs binary64 canoniques) :

> **Si le vérificateur accepte un rapport, alors ce rapport contient toutes les paires de volumes identiques entre A et B, chacune une seule fois, et aucune autre. Réciproquement, tout rapport exact est accepté.**

| Théorème | Énoncé |
|---|---|
| `verifier_correct` | `Contrat verifier` : accepté ⇔ rapport exact |
| `verifierCle_correct` | `ContratParCles verifierCle` : idem après préfiltrage par clé, pour **toute** clé, y compris constante |

La définition exacte est dans [`Probatio/Spec.lean`](Probatio/Spec.lean) (une page). Les démonstrations sont dans [`Probatio/Verificateur.lean`](Probatio/Verificateur.lean). Les hypothèses d'admissibilité des lots ne sont pas utilisées : le résultat tient pour tous les lots.

Le contrôle d'intégration continue (onglet *Actions*) vérifie à chaque modification :
- la compilation et la vérification des preuves par le noyau Lean ;
- l'absence de `sorry`, `admit` ou `native_decide` ;
- la liste des axiomes utilisés (`Axiomes.lean`).

## Ce qui n'est pas démontré

- **La propreté du jeu de données.** Le théorème porte sur l'identité exacte de contenu. Un volume rééchantillonné, recadré, renormalisé ou augmenté, ou deux examens d'un même patient, ne sont pas des volumes identiques et échappent à ce contrôle par construction.
- **La lecture des fichiers.** Le théorème porte sur des volumes déjà décodés. La lecture des fichiers NIfTI-1 et leur conversion en valeurs canoniques sont faites par le vérificateur Python du dossier [`python/`](python/), qui est **testé, pas démontré**.
- **L'inventaire.** Le vérificateur contrôle les fichiers déclarés dans le manifeste remis par le client. Que ce manifeste corresponde au jeu d'entraînement réellement utilisé reste une déclaration du client.

La variante Lean parcourt les candidats et vérifie la clé avant de comparer les volumes. Le code Python utilise des groupes et des représentants. Aucune preuve d’équivalence entre ces deux implémentations n’est fournie. Les théorèmes concernent les fonctions Lean, sur les mots déjà décodés.

## Rejouer

**Preuve Lean** (avec [elan](https://github.com/leanprover/elan) installé) :

```sh
lake build                    # compile et vérifie les preuves, contrôle les verdicts de la démo
lake env lean Axiomes.lean > axiomes.txt && python3 scripts/verifier_axiomes.py axiomes.txt
```

**Vérificateur Python sur fichiers NIfTI-1** (Python 3.10+ et NumPy) :

```sh
cd python
python -B verifier_flux.py exemple/manifeste.json exemple/rapports/exact.json     # accepté
python -B verifier_flux.py exemple/manifeste.json exemple/rapports/omission.json  # rejeté : 1 paire manquante
python -B verifier_flux.py exemple/manifeste.json exemple/rapports/ajout.json     # rejeté : 1 paire en trop
python -B -m unittest -v test_flux
```

Codes de sortie : 0 rapport accepté, 1 rapport rejeté, 2 contrôle incomplet (fichier attendu absent, modifié ou hors profil).

## Périmètre du lecteur Python

NIfTI-1 `.nii` non compressé, scalaire 3D, huit types entiers ou flottants, petit et grand boutisme ; au plus 1 000 fichiers et 20 Go par contrôle. Égalité : même forme XYZ et mêmes valeurs décodées (pente puis ordonnée en binary64, zéro normalisé), indépendamment du type de stockage.

---

PROBATIO · ZTI-Technologies · [zti-probatio.com](https://zti-probatio.com)

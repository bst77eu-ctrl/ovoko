"""Mesure la fiabilité de lecture du module d'extraction.

Compare, capture par capture, la sortie du modèle aux valeurs notées à la
main dans verite_terrain.yaml. Trois issues par champ :

- correct   : la valeur extraite égale la valeur réelle (ou null attendu
              et null obtenu — le modèle a eu raison de ne pas inventer)
- manque    : la valeur était lisible mais le modèle a répondu null
              (prudence excessive : gênant mais sans danger, on corrige
              à la main)
- erreur    : le modèle a produit une valeur différente de la réalité
              (le cas dangereux : une lecture fausse qui a l'air vraie)

Usage :
    export ANTHROPIC_API_KEY=...
    python eval/evaluer_extraction.py
"""

from __future__ import annotations

import base64
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction import extraire_depuis_image  # noqa: E402

DOSSIER = Path(__file__).resolve().parent
CHAMPS_COMPARES = (
    "instrument",
    "timeframe",
    "prix_actuel",
    "plus_haut_visible",
    "plus_bas_visible",
    "tendance_visuelle",
)
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}


def comparer(attendu, obtenu) -> str:
    if attendu is None:
        return "correct" if obtenu is None else "erreur"
    if obtenu is None:
        return "manque"
    if isinstance(attendu, (int, float)) and isinstance(obtenu, (int, float)):
        egal = abs(float(attendu) - float(obtenu)) <= 1e-6 * max(1.0, abs(float(attendu)))
    else:
        egal = str(attendu).strip().lower() == str(obtenu).strip().lower()
    return "correct" if egal else "erreur"


def main() -> int:
    verite = yaml.safe_load((DOSSIER / "verite_terrain.yaml").read_text(encoding="utf-8"))
    entrees = (verite or {}).get("captures") or []
    if not entrees:
        print("Aucune capture déclarée dans eval/verite_terrain.yaml — rien à évaluer.")
        print("Ajoutez vos captures dans eval/captures/ puis décrivez-les dans le YAML.")
        return 1

    totaux = Counter()
    par_champ: dict[str, Counter] = {champ: Counter() for champ in CHAMPS_COMPARES}

    for entree in entrees:
        chemin = DOSSIER / "captures" / entree["fichier"]
        if not chemin.exists():
            print(f"⚠  {entree['fichier']} : fichier absent, capture ignorée")
            continue
        media_type = MEDIA_TYPES.get(chemin.suffix.lower())
        if media_type is None:
            print(f"⚠  {entree['fichier']} : extension non prise en charge")
            continue
        image_b64 = base64.b64encode(chemin.read_bytes()).decode()
        extraction = extraire_depuis_image(image_b64, media_type)

        print(f"\n── {entree['fichier']} (fiabilité annoncée : "
              f"{extraction['fiabilite_lecture']:.2f})")
        for champ in CHAMPS_COMPARES:
            if champ not in entree:
                continue
            verdict = comparer(entree[champ], extraction[champ])
            totaux[verdict] += 1
            par_champ[champ][verdict] += 1
            symbole = {"correct": "✓", "manque": "∅", "erreur": "✗"}[verdict]
            print(f"   {symbole} {champ:<20} attendu={entree[champ]!r} "
                  f"obtenu={extraction[champ]!r}")

    nombre = sum(totaux.values())
    if nombre == 0:
        print("Aucun champ comparé.")
        return 1

    print("\n══ Bilan ══")
    print(f"champs comparés : {nombre}")
    for verdict in ("correct", "manque", "erreur"):
        print(f"  {verdict:<8}: {totaux[verdict]:>3}  ({totaux[verdict] / nombre:.0%})")
    print("\nPar champ (correct/manque/erreur) :")
    for champ, compteur in par_champ.items():
        if sum(compteur.values()):
            print(f"  {champ:<20} {compteur['correct']}/{compteur['manque']}/{compteur['erreur']}")
    print("\nRappel : « manque » se corrige à la main ; « erreur » est le cas "
          "dangereux à surveiller.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

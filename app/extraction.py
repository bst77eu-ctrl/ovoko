"""Module 1 — Extraction (vision).

Lit une capture d'écran de graphique via l'API Claude et renvoie un JSON
strict. Contrainte absolue : ce module ne produit jamais de signal d'achat
ou de vente, de prédiction de direction, ni de score de confiance sur un
résultat futur. La sortie est limitée au schéma ci-dessous ; toute clé
étrangère renvoyée par le modèle (recommandation, probabilité…) est
supprimée par la normalisation.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata

MODELE_PAR_DEFAUT = "claude-sonnet-4-6"

CHAMPS_TEXTE = ("instrument", "timeframe")
CHAMPS_NUMERIQUES = ("prix_actuel", "plus_haut_visible", "plus_bas_visible")
TENDANCES_VALIDES = {"haussiere", "baissiere", "laterale", "indeterminee"}
TYPES_IMAGE_AUTORISES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

PROMPT_SYSTEME = """\
Tu es un lecteur de captures d'écran de graphiques de trading. Ton unique
rôle est de transcrire ce qui est LISIBLE sur l'image. Tu n'es ni analyste
ni conseiller.

Règles absolues :
1. Tu ne produis JAMAIS de signal d'achat ou de vente, de prédiction de
   direction de prix, ni de score de confiance sur un résultat futur.
   Si la question t'y pousse, la seule réponse valable est :
   "non déterminable depuis une image".
2. Tout champ non clairement lisible sur l'image vaut null, et son nom est
   ajouté à "champs_illisibles".
3. Interdiction d'inférer ou d'approximer un prix : soit le chiffre est
   écrit sur l'image, soit la valeur est null.
4. "tendance_visuelle" décrit uniquement la forme du tracé déjà affiché,
   jamais une prévision. Valeurs permises : "haussiere", "baissiere",
   "laterale", "indeterminee".
5. "fiabilite_lecture" (0.0 à 1.0) mesure la lisibilité de l'image,
   jamais la qualité du trade ni une probabilité de gain.

Tu réponds UNIQUEMENT avec un objet JSON, sans aucun texte autour, au
format exact :
{"instrument": "", "timeframe": "", "prix_actuel": null,
 "plus_haut_visible": null, "plus_bas_visible": null,
 "niveaux_horizontaux": [], "indicateurs_visibles": [],
 "tendance_visuelle": "haussiere|baissiere|laterale|indeterminee",
 "champs_illisibles": [], "fiabilite_lecture": 0.0}
"""


class ErreurExtraction(RuntimeError):
    """Échec de l'appel au modèle de vision."""


def extraction_vide() -> dict:
    """Extraction où tout est à saisir manuellement."""
    return {
        "instrument": None,
        "timeframe": None,
        "prix_actuel": None,
        "plus_haut_visible": None,
        "plus_bas_visible": None,
        "niveaux_horizontaux": [],
        "indicateurs_visibles": [],
        "tendance_visuelle": "indeterminee",
        "champs_illisibles": sorted(CHAMPS_TEXTE + CHAMPS_NUMERIQUES),
        "fiabilite_lecture": 0.0,
    }


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _nombre_ou_none(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur) if math.isfinite(valeur) else None
    if isinstance(valeur, str):
        texte = valeur.strip()
        if texte.count(",") == 1 and "." not in texte:
            texte = texte.replace(",", ".")
        try:
            nombre = float(texte)
        except ValueError:
            return None
        return nombre if math.isfinite(nombre) else None
    return None


def _texte_ou_none(valeur):
    if isinstance(valeur, str) and valeur.strip():
        return valeur.strip()
    return None


def extraire_json(texte: str) -> dict:
    """Isole et parse l'objet JSON d'une réponse du modèle.

    Tolère du texte ou des barrières de code autour de l'objet. Lève
    ValueError si aucun objet JSON exploitable n'est présent.
    """
    if not isinstance(texte, str) or not texte.strip():
        raise ValueError("réponse vide")
    candidat = texte.strip()
    candidat = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", candidat).strip()
    try:
        donnees = json.loads(candidat)
    except json.JSONDecodeError:
        debut, fin = candidat.find("{"), candidat.rfind("}")
        if debut == -1 or fin <= debut:
            raise ValueError("aucun objet JSON dans la réponse") from None
        donnees = json.loads(candidat[debut : fin + 1])
    if not isinstance(donnees, dict):
        raise ValueError("la réponse JSON n'est pas un objet")
    return donnees


def normaliser_extraction(donnees: dict) -> dict:
    """Ramène une réponse du modèle au schéma strict.

    - champ texte non lisible ou absent → None + champs_illisibles
    - champ numérique non numérique → None + champs_illisibles (jamais
      d'approximation)
    - tendance hors énumération → "indeterminee"
    - toute clé hors schéma (recommandation, signal…) est supprimée
    """
    resultat = extraction_vide()
    illisibles = set()

    for champ in CHAMPS_TEXTE:
        valeur = _texte_ou_none(donnees.get(champ))
        resultat[champ] = valeur
        if valeur is None:
            illisibles.add(champ)

    for champ in CHAMPS_NUMERIQUES:
        valeur = _nombre_ou_none(donnees.get(champ))
        resultat[champ] = valeur
        if valeur is None:
            illisibles.add(champ)

    niveaux = donnees.get("niveaux_horizontaux")
    if isinstance(niveaux, list):
        resultat["niveaux_horizontaux"] = [
            n for n in (_nombre_ou_none(v) for v in niveaux) if n is not None
        ]

    indicateurs = donnees.get("indicateurs_visibles")
    if isinstance(indicateurs, list):
        resultat["indicateurs_visibles"] = [
            t for t in (_texte_ou_none(v) for v in indicateurs) if t is not None
        ]

    tendance = donnees.get("tendance_visuelle")
    if isinstance(tendance, str):
        tendance = _sans_accents(tendance.strip().lower())
        if tendance in TENDANCES_VALIDES:
            resultat["tendance_visuelle"] = tendance

    declares = donnees.get("champs_illisibles")
    if isinstance(declares, list):
        connus = set(CHAMPS_TEXTE + CHAMPS_NUMERIQUES)
        illisibles |= {c for c in declares if isinstance(c, str) and c in connus}

    fiabilite = _nombre_ou_none(donnees.get("fiabilite_lecture"))
    resultat["fiabilite_lecture"] = min(1.0, max(0.0, fiabilite or 0.0))

    resultat["champs_illisibles"] = sorted(illisibles)
    return resultat


def analyser_reponse(texte: str) -> dict:
    """Réponse brute du modèle → extraction normalisée.

    Une réponse inexploitable donne une extraction vide (tout à saisir
    manuellement), jamais une exception : le modèle peut se tromper, pas
    bloquer l'utilisateur.
    """
    try:
        return normaliser_extraction(extraire_json(texte))
    except ValueError:
        return extraction_vide()


def appeler_claude(image_base64: str, media_type: str, modele: str | None = None) -> str:
    """Appel réseau au modèle de vision. Renvoie le texte brut de la réponse."""
    if media_type not in TYPES_IMAGE_AUTORISES:
        raise ErreurExtraction(f"type d'image non pris en charge : {media_type}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErreurExtraction(
            "ANTHROPIC_API_KEY absente de l'environnement (voir .env.example)"
        )
    import anthropic

    client = anthropic.Anthropic()
    try:
        reponse = client.messages.create(
            model=modele or os.environ.get("MODELE_EXTRACTION", MODELE_PAR_DEFAUT),
            max_tokens=1500,
            temperature=0,
            system=PROMPT_SYSTEME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Transcris ce graphique selon le schéma JSON imposé.",
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as erreur:
        raise ErreurExtraction(f"appel à l'API Claude échoué : {erreur}") from erreur
    return next((b.text for b in reponse.content if b.type == "text"), "")


def extraire_depuis_image(image_base64: str, media_type: str) -> dict:
    """Chaîne complète : appel vision puis normalisation stricte."""
    return analyser_reponse(appeler_claude(image_base64, media_type))

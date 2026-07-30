"""Module 2 — Calcul de risque.

Calcul déterministe de la taille de position, de la perte maximale et du
ratio risque/rendement. Pur calcul arithmétique : aucune donnée n'est
jamais déléguée au modèle de langage.

Le sens du trade est déduit de la position du stop par rapport à l'entrée :
stop sous l'entrée → long, stop au-dessus → short.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class ErreurValidation(ValueError):
    """Entrée invalide pour le calcul de risque."""


@dataclass(frozen=True)
class ResultatRisque:
    sens: str  # "long" ou "short"
    taille_position: float  # en unités de l'instrument
    risque_par_unite: float  # distance entre l'entrée et le stop
    perte_max: float  # en euros, si le stop est touché
    gain_potentiel: float | None  # en euros, si un objectif est fourni
    ratio_risque_rendement: float | None  # gain potentiel / perte max


def _nombre(valeur, nom: str) -> float:
    if isinstance(valeur, bool):
        raise ErreurValidation(f"{nom} doit être un nombre")
    try:
        resultat = float(valeur)
    except (TypeError, ValueError):
        raise ErreurValidation(f"{nom} doit être un nombre") from None
    if not math.isfinite(resultat):
        raise ErreurValidation(f"{nom} doit être un nombre fini")
    return resultat


def calculer_risque(
    capital,
    risque_pct,
    prix_entree,
    stop_loss,
    objectif=None,
) -> ResultatRisque:
    """Calcule la taille de position pour un capital et un risque donnés.

    capital : capital total du compte, en euros (> 0)
    risque_pct : risque maximal par trade, en pourcentage (0 < x <= 100)
    prix_entree : prix d'entrée prévu (> 0)
    stop_loss : niveau du stop (> 0, différent de l'entrée)
    objectif : niveau de prise de profit, optionnel ; doit se trouver du
        côté profitable du trade (au-dessus de l'entrée pour un long,
        en dessous pour un short)
    """
    capital = _nombre(capital, "capital")
    risque_pct = _nombre(risque_pct, "risque_pct")
    prix_entree = _nombre(prix_entree, "prix_entree")
    stop_loss = _nombre(stop_loss, "stop_loss")

    if capital <= 0:
        raise ErreurValidation("le capital doit être strictement positif")
    if not 0 < risque_pct <= 100:
        raise ErreurValidation(
            "le risque par trade doit être compris entre 0 (exclu) et 100 %"
        )
    if prix_entree <= 0:
        raise ErreurValidation("le prix d'entrée doit être strictement positif")
    if stop_loss <= 0:
        raise ErreurValidation("le stop-loss doit être strictement positif")
    if stop_loss == prix_entree:
        raise ErreurValidation(
            "le stop-loss ne peut pas être égal au prix d'entrée"
        )

    sens = "long" if stop_loss < prix_entree else "short"
    risque_par_unite = abs(prix_entree - stop_loss)
    perte_max = capital * risque_pct / 100
    taille_position = perte_max / risque_par_unite

    gain_potentiel = None
    ratio = None
    if objectif is not None:
        objectif = _nombre(objectif, "objectif")
        if objectif <= 0:
            raise ErreurValidation("l'objectif doit être strictement positif")
        if sens == "long" and objectif <= prix_entree:
            raise ErreurValidation(
                "trade long : l'objectif doit être au-dessus du prix d'entrée"
            )
        if sens == "short" and objectif >= prix_entree:
            raise ErreurValidation(
                "trade short : l'objectif doit être en dessous du prix d'entrée"
            )
        gain_par_unite = abs(objectif - prix_entree)
        gain_potentiel = taille_position * gain_par_unite
        ratio = gain_par_unite / risque_par_unite

    return ResultatRisque(
        sens=sens,
        taille_position=taille_position,
        risque_par_unite=risque_par_unite,
        perte_max=perte_max,
        gain_potentiel=gain_potentiel,
        ratio_risque_rendement=ratio,
    )

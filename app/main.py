"""Serveur FastAPI — assemble les quatre modules et sert le frontend.

Le calcul de risque et la validation de la checklist sont toujours
refaits côté serveur : le frontend n'est qu'une vue, jamais une source
de vérité.
"""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import checklist as module_checklist
from app import extraction as module_extraction
from app import stats as module_stats
from app.journal import ErreurJournal, Journal
from app.risque import ErreurValidation, calculer_risque

RACINE = Path(__file__).resolve().parent.parent
TAILLE_MAX_CAPTURE = 10 * 1024 * 1024  # 10 Mo


def charger_env(chemin: Path) -> None:
    """Charge un .env minimal (KEY=VALUE) sans écraser l'environnement."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip())


class RequeteRisque(BaseModel):
    capital: Any = None
    risque_pct: Any = None
    prix_entree: Any = None
    stop_loss: Any = None
    objectif: Any = None


class RequeteExtraction(BaseModel):
    image_base64: str
    media_type: str


class RequeteTrade(BaseModel):
    capture_base64: str
    capture_media_type: str
    extraction: dict
    checklist: dict
    risque: RequeteRisque


class RequeteResultat(BaseModel):
    resultat_eur: Any = None


def _calcul_risque_ou_400(requete: RequeteRisque) -> dict:
    try:
        resultat = calculer_risque(
            capital=requete.capital,
            risque_pct=requete.risque_pct,
            prix_entree=requete.prix_entree,
            stop_loss=requete.stop_loss,
            objectif=requete.objectif if requete.objectif not in (None, "") else None,
        )
    except ErreurValidation as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from None
    return {
        "entrees": {
            "capital": float(requete.capital),
            "risque_pct": float(requete.risque_pct),
            "prix_entree": float(requete.prix_entree),
            "stop_loss": float(requete.stop_loss),
            "objectif": float(requete.objectif)
            if requete.objectif not in (None, "")
            else None,
        },
        "sens": resultat.sens,
        "taille_position": resultat.taille_position,
        "risque_par_unite": resultat.risque_par_unite,
        "perte_max": resultat.perte_max,
        "gain_potentiel": resultat.gain_potentiel,
        "ratio_risque_rendement": resultat.ratio_risque_rendement,
    }


def creer_app(
    dossier_donnees: str | Path | None = None,
    chemin_checklist: str | Path | None = None,
) -> FastAPI:
    charger_env(RACINE / ".env")
    dossier_donnees = Path(dossier_donnees or os.environ.get("DOSSIER_DONNEES", RACINE / "data"))
    chemin_checklist = Path(
        chemin_checklist or os.environ.get("CHEMIN_CHECKLIST", RACINE / "checklist.yaml")
    )

    application = FastAPI(
        title="Assistant de pré-trade",
        description="Outil d'aide à la discipline. Aucune recommandation d'investissement.",
    )
    journal = Journal(dossier_donnees)
    application.mount(
        "/captures", StaticFiles(directory=journal.dossier_captures), name="captures"
    )

    def questions() -> list[dict]:
        try:
            return module_checklist.charger_checklist(chemin_checklist)
        except module_checklist.ErreurChecklist as erreur:
            raise HTTPException(status_code=500, detail=str(erreur)) from None

    @application.get("/")
    def accueil() -> FileResponse:
        return FileResponse(RACINE / "static" / "index.html")

    @application.get("/api/checklist")
    def lire_checklist() -> dict:
        return {"questions": questions()}

    @application.post("/api/risque")
    def calculer(requete: RequeteRisque) -> dict:
        return _calcul_risque_ou_400(requete)

    @application.post("/api/extraction")
    def extraire(requete: RequeteExtraction) -> dict:
        if requete.media_type not in module_extraction.TYPES_IMAGE_AUTORISES:
            raise HTTPException(
                status_code=400,
                detail=f"type d'image non pris en charge : {requete.media_type}",
            )
        try:
            texte = module_extraction.appeler_claude(
                requete.image_base64, requete.media_type
            )
        except module_extraction.ErreurExtraction as erreur:
            raise HTTPException(status_code=502, detail=str(erreur)) from None
        return {"extraction": module_extraction.analyser_reponse(texte)}

    @application.post("/api/trades", status_code=201)
    def enregistrer_trade(requete: RequeteTrade) -> dict:
        try:
            reponses = module_checklist.valider_reponses(questions(), requete.checklist)
        except module_checklist.ErreurChecklist as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from None
        risque = _calcul_risque_ou_400(requete.risque)
        if requete.capture_media_type not in module_extraction.TYPES_IMAGE_AUTORISES:
            raise HTTPException(
                status_code=400,
                detail=f"type d'image non pris en charge : {requete.capture_media_type}",
            )
        try:
            capture = base64.b64decode(requete.capture_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="capture base64 invalide") from None
        if not capture or len(capture) > TAILLE_MAX_CAPTURE:
            raise HTTPException(status_code=400, detail="capture vide ou trop lourde (max 10 Mo)")
        identifiant = journal.enregistrer_trade(
            extraction=module_extraction.normaliser_extraction(requete.extraction),
            checklist=reponses,
            risque=risque,
            capture=capture,
            capture_media_type=requete.capture_media_type,
        )
        return {"id": identifiant}

    @application.get("/api/trades")
    def lister_trades() -> dict:
        return {"trades": journal.lister_trades()}

    @application.post("/api/trades/{identifiant}/resultat")
    def enregistrer_resultat(identifiant: int, requete: RequeteResultat) -> dict:
        try:
            journal.enregistrer_resultat(identifiant, requete.resultat_eur)
        except ErreurJournal as erreur:
            code = 404 if "introuvable" in str(erreur) else 400
            raise HTTPException(status_code=code, detail=str(erreur)) from None
        return {"trade": journal.obtenir_trade(identifiant)}

    @application.get("/api/stats")
    def statistiques() -> dict:
        return module_stats.calculer_stats(journal.lister_trades(), questions())

    return application


app = creer_app()

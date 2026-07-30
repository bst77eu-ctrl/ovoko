"""Module 4 — Journal des trades (SQLite).

Chaque trade enregistre la capture d'écran, les données extraites (telles
que corrigées par l'utilisateur), les réponses à la checklist, le calcul
de risque et l'horodatage. Le résultat en euros est saisi après clôture ;
le résultat en R (multiples du risque initial) est dérivé à la lecture.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage TEXT NOT NULL,
    capture_chemin TEXT,
    extraction TEXT NOT NULL,
    checklist TEXT NOT NULL,
    risque TEXT NOT NULL,
    resultat_eur REAL,
    cloture_horodatage TEXT
);
"""

EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


class ErreurJournal(ValueError):
    """Opération invalide sur le journal."""


def _maintenant() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Journal:
    def __init__(self, dossier_donnees: str | Path):
        self.dossier = Path(dossier_donnees)
        self.dossier_captures = self.dossier / "captures"
        self.dossier_captures.mkdir(parents=True, exist_ok=True)
        self.chemin_db = self.dossier / "journal.db"
        with self._connexion() as connexion:
            connexion.executescript(SCHEMA)

    def _connexion(self) -> sqlite3.Connection:
        connexion = sqlite3.connect(self.chemin_db)
        connexion.row_factory = sqlite3.Row
        return connexion

    def enregistrer_trade(
        self,
        extraction: dict,
        checklist: dict,
        risque: dict,
        capture: bytes | None = None,
        capture_media_type: str | None = None,
    ) -> int:
        with self._connexion() as connexion:
            curseur = connexion.execute(
                "INSERT INTO trades (horodatage, extraction, checklist, risque)"
                " VALUES (?, ?, ?, ?)",
                (
                    _maintenant(),
                    json.dumps(extraction, ensure_ascii=False),
                    json.dumps(checklist, ensure_ascii=False),
                    json.dumps(risque, ensure_ascii=False),
                ),
            )
            identifiant = curseur.lastrowid
            if capture is not None:
                extension = EXTENSIONS.get(capture_media_type or "", "png")
                nom_fichier = f"{identifiant}.{extension}"
                (self.dossier_captures / nom_fichier).write_bytes(capture)
                connexion.execute(
                    "UPDATE trades SET capture_chemin = ? WHERE id = ?",
                    (nom_fichier, identifiant),
                )
        return identifiant

    def enregistrer_resultat(self, identifiant: int, resultat_eur) -> None:
        try:
            resultat = float(resultat_eur)
        except (TypeError, ValueError):
            raise ErreurJournal("le résultat doit être un nombre (en euros)") from None
        if not math.isfinite(resultat):
            raise ErreurJournal("le résultat doit être un nombre fini")
        with self._connexion() as connexion:
            curseur = connexion.execute(
                "UPDATE trades SET resultat_eur = ?, cloture_horodatage = ? WHERE id = ?",
                (resultat, _maintenant(), identifiant),
            )
            if curseur.rowcount == 0:
                raise ErreurJournal(f"trade introuvable : {identifiant}")

    def lister_trades(self) -> list[dict]:
        with self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT * FROM trades ORDER BY id DESC"
            ).fetchall()
        return [self._ligne_en_trade(ligne) for ligne in lignes]

    def obtenir_trade(self, identifiant: int) -> dict:
        with self._connexion() as connexion:
            ligne = connexion.execute(
                "SELECT * FROM trades WHERE id = ?", (identifiant,)
            ).fetchone()
        if ligne is None:
            raise ErreurJournal(f"trade introuvable : {identifiant}")
        return self._ligne_en_trade(ligne)

    @staticmethod
    def _ligne_en_trade(ligne: sqlite3.Row) -> dict:
        trade = {
            "id": ligne["id"],
            "horodatage": ligne["horodatage"],
            "capture_chemin": ligne["capture_chemin"],
            "extraction": json.loads(ligne["extraction"]),
            "checklist": json.loads(ligne["checklist"]),
            "risque": json.loads(ligne["risque"]),
            "resultat_eur": ligne["resultat_eur"],
            "cloture_horodatage": ligne["cloture_horodatage"],
            "resultat_r": None,
        }
        perte_max = trade["risque"].get("perte_max")
        if trade["resultat_eur"] is not None and perte_max:
            trade["resultat_r"] = trade["resultat_eur"] / perte_max
        return trade

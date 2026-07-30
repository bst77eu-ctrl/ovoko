import math

import pytest

from app.risque import ErreurValidation, calculer_risque


class TestTradeLong:
    def test_taille_position(self):
        r = calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95)
        assert r.sens == "long"
        assert r.perte_max == pytest.approx(100.0)
        assert r.risque_par_unite == pytest.approx(5.0)
        assert r.taille_position == pytest.approx(20.0)

    def test_sans_objectif_pas_de_ratio(self):
        r = calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95)
        assert r.gain_potentiel is None
        assert r.ratio_risque_rendement is None

    def test_avec_objectif(self):
        r = calculer_risque(
            capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95, objectif=110
        )
        assert r.ratio_risque_rendement == pytest.approx(2.0)
        assert r.gain_potentiel == pytest.approx(200.0)

    def test_petits_prix_type_forex(self):
        r = calculer_risque(
            capital=5_000, risque_pct=2, prix_entree=1.0850, stop_loss=1.0800
        )
        assert r.perte_max == pytest.approx(100.0)
        assert r.risque_par_unite == pytest.approx(0.005)
        assert r.taille_position == pytest.approx(20_000.0)

    def test_perte_reelle_egale_perte_max(self):
        r = calculer_risque(
            capital=7_531, risque_pct=1.5, prix_entree=42.37, stop_loss=41.02
        )
        assert r.taille_position * r.risque_par_unite == pytest.approx(r.perte_max)


class TestTradeShort:
    def test_stop_au_dessus_de_l_entree_est_un_short(self):
        r = calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=105)
        assert r.sens == "short"
        assert r.risque_par_unite == pytest.approx(5.0)
        assert r.taille_position == pytest.approx(20.0)

    def test_avec_objectif(self):
        r = calculer_risque(
            capital=10_000, risque_pct=1, prix_entree=100, stop_loss=105, objectif=90
        )
        assert r.ratio_risque_rendement == pytest.approx(2.0)
        assert r.gain_potentiel == pytest.approx(200.0)

    def test_objectif_au_dessus_de_l_entree_refuse(self):
        with pytest.raises(ErreurValidation, match="short"):
            calculer_risque(
                capital=10_000, risque_pct=1, prix_entree=100, stop_loss=105, objectif=110
            )


class TestCapital:
    def test_capital_nul(self):
        with pytest.raises(ErreurValidation, match="capital"):
            calculer_risque(capital=0, risque_pct=1, prix_entree=100, stop_loss=95)

    def test_capital_negatif(self):
        with pytest.raises(ErreurValidation, match="capital"):
            calculer_risque(capital=-500, risque_pct=1, prix_entree=100, stop_loss=95)

    def test_capital_infini(self):
        with pytest.raises(ErreurValidation, match="fini"):
            calculer_risque(
                capital=math.inf, risque_pct=1, prix_entree=100, stop_loss=95
            )

    def test_capital_nan(self):
        with pytest.raises(ErreurValidation, match="fini"):
            calculer_risque(
                capital=math.nan, risque_pct=1, prix_entree=100, stop_loss=95
            )


class TestRisquePct:
    def test_risque_nul(self):
        with pytest.raises(ErreurValidation, match="risque"):
            calculer_risque(capital=10_000, risque_pct=0, prix_entree=100, stop_loss=95)

    def test_risque_negatif(self):
        with pytest.raises(ErreurValidation, match="risque"):
            calculer_risque(capital=10_000, risque_pct=-1, prix_entree=100, stop_loss=95)

    def test_risque_superieur_a_cent(self):
        with pytest.raises(ErreurValidation, match="risque"):
            calculer_risque(
                capital=10_000, risque_pct=101, prix_entree=100, stop_loss=95
            )

    def test_risque_cent_pour_cent_accepte(self):
        r = calculer_risque(capital=10_000, risque_pct=100, prix_entree=100, stop_loss=95)
        assert r.perte_max == pytest.approx(10_000.0)


class TestPrix:
    def test_stop_egal_a_l_entree(self):
        with pytest.raises(ErreurValidation, match="égal"):
            calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=100)

    def test_prix_entree_nul(self):
        with pytest.raises(ErreurValidation, match="entrée"):
            calculer_risque(capital=10_000, risque_pct=1, prix_entree=0, stop_loss=95)

    def test_prix_entree_negatif(self):
        with pytest.raises(ErreurValidation, match="entrée"):
            calculer_risque(capital=10_000, risque_pct=1, prix_entree=-100, stop_loss=95)

    def test_stop_nul(self):
        with pytest.raises(ErreurValidation, match="stop"):
            calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=0)

    def test_stop_negatif(self):
        with pytest.raises(ErreurValidation, match="stop"):
            calculer_risque(capital=10_000, risque_pct=1, prix_entree=100, stop_loss=-5)


class TestObjectif:
    def test_objectif_egal_a_l_entree_refuse(self):
        with pytest.raises(ErreurValidation, match="objectif"):
            calculer_risque(
                capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95, objectif=100
            )

    def test_objectif_du_mauvais_cote_pour_un_long(self):
        with pytest.raises(ErreurValidation, match="long"):
            calculer_risque(
                capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95, objectif=97
            )

    def test_objectif_nul(self):
        with pytest.raises(ErreurValidation, match="objectif"):
            calculer_risque(
                capital=10_000, risque_pct=1, prix_entree=100, stop_loss=95, objectif=0
            )


class TestEntreesNonNumeriques:
    def test_texte(self):
        with pytest.raises(ErreurValidation, match="nombre"):
            calculer_risque(capital="abc", risque_pct=1, prix_entree=100, stop_loss=95)

    def test_none(self):
        with pytest.raises(ErreurValidation, match="nombre"):
            calculer_risque(capital=None, risque_pct=1, prix_entree=100, stop_loss=95)

    def test_booleen(self):
        with pytest.raises(ErreurValidation, match="nombre"):
            calculer_risque(capital=True, risque_pct=1, prix_entree=100, stop_loss=95)

    def test_chaine_numerique_acceptee(self):
        # Les valeurs arrivent du formulaire HTML, souvent en texte.
        r = calculer_risque(capital="10000", risque_pct="1", prix_entree="100", stop_loss="95")
        assert r.taille_position == pytest.approx(20.0)

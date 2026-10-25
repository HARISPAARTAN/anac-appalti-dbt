import pytest

from anac_appalti.archivio import estrai_pacchetto
from anac_appalti.ckan import crea_fonte
from anac_appalti.config import carica_impostazioni
from anac_appalti.contratti import carica_contratti
from anac_appalti.landing import atterra_pacchetto, leggi_registro

pytestmark = pytest.mark.integrazione


def esegui(imp):
    fonte = crea_fonte(imp)
    contratti = carica_contratti(imp.contratti_dir)
    estratti = {p.tabella: estrai_pacchetto(imp, fonte, p) for p in imp.pacchetti}
    atterrati = {p.tabella: atterra_pacchetto(imp, p, contratti[p.tabella]) for p in imp.pacchetti}
    return estratti, atterrati


def test_estrazione_idempotente_e_delta(tmp_path):
    imp1 = carica_impostazioni(fixtures=True, mese=1, area=tmp_path)
    estratti, atterrati = esegui(imp1)
    assert sum(e.scaricati for e in estratti.values()) == 18
    assert estratti["cig"].pacchetti_assenti == []
    assert all(a.errori == [] for a in atterrati.values())
    registro = {v.risorsa: v for v in leggi_registro(imp1.registro_file)}
    assert registro["aggiudicazioni_csv"].righe == "1200"
    assert registro["aggiudicazioni_csv"].riconciliazione == "ok"
    assert registro["cig_csv_2025_01"].righe == "828"
    assert registro["cig_csv_2025_01"].riconciliazione == "non_disponibile"
    assert registro["cig_csv_2025_01"].data_snapshot == "2026-01-16"

    estratti, atterrati = esegui(imp1)
    assert sum(e.scaricati for e in estratti.values()) == 0
    assert sum(a.atterrati for a in atterrati.values()) == 0

    imp2 = carica_impostazioni(fixtures=True, mese=2, area=tmp_path)
    estratti, atterrati = esegui(imp2)
    assert estratti["cig"].scaricati == 2
    assert sum(e.scaricati for e in estratti.values()) == 2
    assert atterrati["cig"].righe == {"20260401-cig_csv": 51}
    delta = {v.risorsa: v for v in leggi_registro(imp2.registro_file)}["20260401-cig_csv"]
    assert (delta.riconciliazione, delta.data_snapshot) == ("ok", "2026-04-01")

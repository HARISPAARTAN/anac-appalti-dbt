import io
import zipfile

from anac_appalti.intestazioni import (
    CAMPIONI,
    intestazione_da_zip_parziale,
    rileva_intestazioni,
    url_download,
)

INTESTAZIONE = '"cig";"ruolo";"codice_fiscale";"denominazione";"tipo_soggetto";"id_aggiudicazione"'


def zip_in_memoria(nome: str, testo: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome, testo)
    return buffer.getvalue()


def test_intestazione_dai_primi_byte():
    righe = "\n".join(
        [INTESTAZIONE] + ['"FX00000001";"MANDANTE";"01199250158";"IMPRESA SRL";"IMPRESA";"5"'] * 5000
    )
    dati = zip_in_memoria("20261001-aggiudicatari_csv.csv", righe + "\n")
    info = intestazione_da_zip_parziale(dati[:4096])
    assert info["file_interno"] == "20261001-aggiudicatari_csv.csv"
    assert info["delimitatore"] == ";"
    assert info["codifica"] == "utf-8"
    assert info["colonne"] == [
        "cig",
        "ruolo",
        "codice_fiscale",
        "denominazione",
        "tipo_soggetto",
        "id_aggiudicazione",
    ]


def test_rileva_intestazioni_con_fonte_finta():
    class FonteFinta:
        user_agent_usato = "prova"

        def package_show(self, nome):
            return {"name": nome}

        def leggi_inizio(self, url, n_byte):
            return zip_in_memoria(url.rsplit("/", 1)[1].replace(".zip", ".csv"), INTESTAZIONE + "\n")[:n_byte]

    risultato = rileva_intestazioni(FonteFinta(), "https://esempio.it/opendata")
    assert set(risultato["tabelle"]) == set(CAMPIONI)
    assert risultato["tabelle"]["cig"]["delta_identico"] is True
    assert risultato["user_agent"] == "prova"
    assert (
        url_download("https://x/opendata", "cig", "a.zip")
        == "https://x/opendata/download/dataset/cig/filesystem/a.zip"
    )

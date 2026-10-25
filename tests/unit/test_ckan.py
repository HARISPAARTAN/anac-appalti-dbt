import json
from pathlib import Path

import httpx
import pytest

from anac_appalti.ckan import (
    ClientCkan,
    ErroreCkan,
    NonTrovato,
    SpecchioLocale,
    WafRifiuto,
    rileva_waf,
    risorse_da_package,
)
from anac_appalti.config import UA_BROWSER, UA_PROGETTO

PAGINA_404 = b"<html><head><title>404 Not Found</title></head><body>Not Found</body></html>"
BASE = "https://dati.anticorruzione.it/opendata"
DL = f"{BASE}/download/dataset/cig-2025/filesystem"
PACCHETTO = {
    "name": "cig-2025",
    "metadata_modified": "2026-01-23T08:20:09.269471",
    "resources": [
        {
            "name": "cig_csv_2025_01",
            "format": "CSV",
            "size": 91942157,
            "last_modified": "2026-01-16T00:00:00",
            "url": f"{DL}/cig_csv_2025_01.zip",
        },
        {
            "name": "cig_json_2025_01",
            "format": "JSON",
            "size": 5,
            "last_modified": "2026-01-16T00:00:00",
            "url": f"{DL}/cig_json_2025_01.zip",
        },
        {
            "name": "cig-2025_csv_logCsv",
            "format": "CSV",
            "size": 1100,
            "last_modified": "2026-01-21T00:00:00",
            "url": f"{DL}/cig-2025_csv_logCsv.csv",
        },
    ],
}
WAF = (
    b"<html><head><title>Request Rejected</title></head><body>The requested URL was rejected. "
    b"Please consult with your administrator.<br/><br/>Your support ID is f2ebc400-2e2c-4981-b585-52602b923c8f"
    b"<br/><br/></body></html>"
)


def client(gestore, **kw) -> ClientCkan:
    return ClientCkan(BASE, UA_PROGETTO, transport=httpx.MockTransport(gestore), attesa=lambda s: None, **kw)


def test_rileva_waf():
    assert rileva_waf(WAF) == "f2ebc400-2e2c-4981-b585-52602b923c8f"
    assert rileva_waf(b'{"success": true}') is None
    assert rileva_waf(b"PK\x03\x04binario") is None


def test_package_show_e_risorse_csv():
    def gestore(req: httpx.Request) -> httpx.Response:
        assert req.url.params["id"] == "cig-2025"
        assert req.headers["user-agent"] == UA_PROGETTO
        return httpx.Response(200, json={"success": True, "result": PACCHETTO})

    risorse = risorse_da_package(client(gestore).package_show("cig-2025"))
    assert [r.file for r in risorse] == ["cig-2025_csv_logCsv.csv", "cig_csv_2025_01.zip"]
    assert risorse[1].dimensione == 91942157
    assert risorse[1].last_modified.isoformat() == "2026-01-16T00:00:00"
    assert risorse[1].pacchetto == "cig-2025"


def test_pacchetto_inesistente_restituisce_none():
    def gestore(req):
        return httpx.Response(
            404, json={"success": False, "error": {"message": "Non trovato", "__type": "Not Found Error"}}
        )

    assert client(gestore).package_show("cig-2026") is None


def test_waf_poi_user_agent_di_riserva():
    visti = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        if req.headers["user-agent"] == UA_PROGETTO:
            return httpx.Response(200, content=WAF, headers={"content-type": "text/html"})
        return httpx.Response(200, json={"success": True, "result": PACCHETTO})

    c = client(gestore)
    assert c.package_show("cig-2025")["name"] == "cig-2025"
    assert visti == [UA_PROGETTO, UA_BROWSER]
    assert c.user_agent_usato == UA_BROWSER


def test_waf_su_entrambi_gli_user_agent():
    def gestore(req):
        return httpx.Response(200, content=WAF, headers={"content-type": "text/html"})

    with pytest.raises(WafRifiuto) as exc:
        client(gestore).package_show("cig-2025")
    assert exc.value.support_id == "f2ebc400-2e2c-4981-b585-52602b923c8f"


def test_ritenta_su_503():
    risposte = iter([httpx.Response(503), httpx.Response(200, json={"success": True, "result": PACCHETTO})])
    attese = []
    c = ClientCkan(
        BASE, UA_PROGETTO, transport=httpx.MockTransport(lambda r: next(risposte)), attesa=attese.append
    )
    assert c.package_show("cig-2025")["name"] == "cig-2025"
    assert attese == [1]


def test_errore_dopo_tentativi_esauriti():
    c = ClientCkan(
        BASE,
        UA_PROGETTO,
        tentativi=2,
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
        attesa=lambda s: None,
    )
    with pytest.raises(ErroreCkan):
        c.package_show("cig-2025")


def test_scarica_scrive_il_file_senza_parziali(tmp_path: Path):
    def gestore(req):
        return httpx.Response(200, content=b"PK\x03\x04dati", headers={"content-type": "application/zip"})

    destinazione = tmp_path / "a" / "x.zip"
    assert client(gestore).scarica(f"{DL}/x.zip", destinazione) == 8
    assert destinazione.read_bytes() == b"PK\x03\x04dati"
    assert not list(tmp_path.rglob("*.part"))


def test_scarica_con_waf_usa_la_riserva(tmp_path: Path):
    def gestore(req):
        if req.headers["user-agent"] == UA_PROGETTO:
            return httpx.Response(200, content=WAF, headers={"content-type": "text/html"})
        return httpx.Response(200, content=b"PK", headers={"content-type": "application/zip"})

    c = client(gestore)
    assert c.scarica(f"{DL}/x.zip", tmp_path / "x.zip") == 2
    assert c.user_agent_usato == UA_BROWSER


def waf_html(req):
    return httpx.Response(200, content=WAF, headers={"content-type": "text/html"})


def ok_json(req):
    return httpx.Response(200, json={"success": True, "result": PACCHETTO})


def test_rileva_waf_solo_con_i_marcatori():
    # Una pagina HTML qualunque non è un rifiuto del WAF.
    assert rileva_waf(PAGINA_404) is None
    assert rileva_waf(b"<!DOCTYPE html><html><body>Errore</body></html>") is None
    # Il WAF si riconosce anche senza HTML di apertura e senza support ID.
    assert rileva_waf(b"Request rejected. Your support ID is: 1234-abcd") == "1234-abcd"
    assert rileva_waf(b"<TITLE>Request Rejected</TITLE>") == "sconosciuto"


def test_pagina_html_404_non_e_un_blocco_waf():
    visti = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        return httpx.Response(404, content=PAGINA_404, headers={"content-type": "text/html"})

    with client(gestore) as c:
        with pytest.raises(NonTrovato) as exc:
            c.package_show("cig-2026")
        assert exc.value.stato == 404
        assert isinstance(exc.value, ErroreCkan)
        assert not isinstance(exc.value, WafRifiuto)
        # Nessun cambio di User-Agent e una sola richiesta: un 404 non si ritenta.
        assert visti == [UA_PROGETTO]
        assert c.user_agent_usato == UA_PROGETTO


def test_scarica_404_html_non_e_waf_e_non_lascia_file(tmp_path: Path):
    def gestore(req):
        return httpx.Response(404, content=PAGINA_404, headers={"content-type": "text/html"})

    with client(gestore) as c:
        with pytest.raises(NonTrovato):
            c.scarica(f"{DL}/x.zip", tmp_path / "x.zip")
        assert c.user_agent_usato == UA_PROGETTO
    assert list(tmp_path.iterdir()) == []


def test_scarica_waf_text_plain_non_diventa_uno_zip(tmp_path: Path):
    def gestore(req):
        return httpx.Response(200, content=WAF, headers={"content-type": "text/plain"})

    with client(gestore) as c:
        with pytest.raises(WafRifiuto) as exc:
            c.scarica(f"{DL}/x.zip", tmp_path / "x.zip")
    assert exc.value.support_id == "f2ebc400-2e2c-4981-b585-52602b923c8f"
    assert list(tmp_path.iterdir()) == []


def test_scarica_waf_text_plain_poi_riserva(tmp_path: Path):
    def gestore(req):
        if req.headers["user-agent"] == UA_PROGETTO:
            return httpx.Response(200, content=WAF, headers={"content-type": "text/plain"})
        return httpx.Response(200, content=b"PKdati", headers={"content-type": "application/zip"})

    with client(gestore) as c:
        assert c.scarica(f"{DL}/x.zip", tmp_path / "x.zip") == 6
    assert (tmp_path / "x.zip").read_bytes() == b"PKdati"


def test_scarica_rifiuta_contenuto_non_zip(tmp_path: Path):
    def gestore(req):
        return httpx.Response(200, content=b"non e uno zip", headers={"content-type": "text/plain"})

    with client(gestore) as c:
        with pytest.raises(ErroreCkan, match="non è uno zip"):
            c.scarica(f"{DL}/x.zip", tmp_path / "x.zip")
    assert list(tmp_path.iterdir()) == []


def test_scarica_csv_non_richiede_la_firma_zip(tmp_path: Path):
    def gestore(req):
        return httpx.Response(200, content=b'"a";"b"\n', headers={"content-type": "text/csv"})

    with client(gestore) as c:
        assert c.scarica(f"{DL}/log.csv", tmp_path / "log.csv") == 8


def test_waf_su_entrambi_fa_due_richieste():
    visti = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        return waf_html(req)

    with client(gestore) as c, pytest.raises(WafRifiuto) as exc:
        c.package_show("cig-2025")
    assert visti == [UA_PROGETTO, UA_BROWSER]
    assert exc.value.user_agent == UA_BROWSER
    assert UA_BROWSER in str(exc.value)


def test_riserva_con_un_solo_tentativo():
    visti = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        return waf_html(req) if req.headers["user-agent"] == UA_PROGETTO else ok_json(req)

    with client(gestore, tentativi=1) as c:
        assert c.package_show("cig-2025")["name"] == "cig-2025"
        assert c.user_agent_usato == UA_BROWSER
    assert visti == [UA_PROGETTO, UA_BROWSER]


def test_errore_finale_nomina_l_ultimo_user_agent():
    visti = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        return waf_html(req) if req.headers["user-agent"] == UA_PROGETTO else httpx.Response(503)

    with client(gestore, tentativi=1) as c, pytest.raises(ErroreCkan) as exc:
        c.package_show("cig-2025")
    assert visti == [UA_PROGETTO, UA_BROWSER]
    assert UA_BROWSER in str(exc.value)
    assert "dopo 1 tentativi" in str(exc.value)


def test_503_poi_waf_poi_riserva_con_due_tentativi():
    visti = []
    attese = []

    def gestore(req):
        visti.append(req.headers["user-agent"])
        if len(visti) == 1:
            return httpx.Response(503)
        return waf_html(req) if req.headers["user-agent"] == UA_PROGETTO else ok_json(req)

    c = ClientCkan(
        BASE, UA_PROGETTO, tentativi=2, transport=httpx.MockTransport(gestore), attesa=attese.append
    )
    with c:
        assert c.package_show("cig-2025")["name"] == "cig-2025"
    assert visti == [UA_PROGETTO, UA_PROGETTO, UA_BROWSER]
    assert attese == [1]


def test_scarica_ritenta_su_503_e_pulisce_i_parziali(tmp_path: Path):
    attese = []
    c = ClientCkan(
        BASE,
        UA_PROGETTO,
        tentativi=2,
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
        attesa=attese.append,
    )
    with c, pytest.raises(ErroreCkan, match="dopo 2 tentativi"):
        c.scarica(f"{DL}/x.zip", tmp_path / "x.zip")
    assert attese == [1]
    assert list(tmp_path.iterdir()) == []


class Flusso(httpx.SyncByteStream):
    """Corpo a blocchi che conta i byte realmente letti dal client."""

    def __init__(self, n_blocchi: int, dimensione: int) -> None:
        self.n_blocchi = n_blocchi
        self.dimensione = dimensione
        self.letti = 0

    def __iter__(self):
        for _ in range(self.n_blocchi):
            self.letti += self.dimensione
            yield b"x" * self.dimensione


def test_leggi_inizio_manda_il_range_e_restituisce_esattamente_n_byte():
    richieste = []

    def gestore(req):
        richieste.append(req.headers["range"])
        return httpx.Response(206, content=b"PK" + b"a" * 5000)

    with client(gestore) as c:
        dati = c.leggi_inizio(f"{DL}/x.zip", 100)
    assert richieste == ["bytes=0-99"]
    assert len(dati) == 100
    assert dati.startswith(b"PK")


def test_leggi_inizio_senza_range_non_legge_il_corpo_intero():
    flusso = Flusso(1000, 1000)

    def gestore(req):
        return httpx.Response(200, stream=flusso)

    with client(gestore) as c, pytest.raises(ErroreCkan, match="206") as exc:
        c.leggi_inizio(f"{DL}/x.zip", 2500)
    assert not isinstance(exc.value, NonTrovato)
    # Un 200 a una richiesta Range è un errore: del milione di byte se ne legge solo la testa.
    assert flusso.letti <= 5000


def test_leggi_inizio_si_ferma_a_n_byte_anche_con_corpo_piu_grande():
    flusso = Flusso(1000, 1000)

    def gestore(req):
        return httpx.Response(206, stream=flusso)

    with client(gestore) as c:
        dati = c.leggi_inizio(f"{DL}/x.zip", 2500)
    assert dati == b"x" * 2500
    assert flusso.letti <= 2500 + 1000


def test_leggi_inizio_404_e_un_errore_del_progetto():
    with client(
        lambda req: httpx.Response(404, content=PAGINA_404, headers={"content-type": "text/html"})
    ) as c:
        with pytest.raises(NonTrovato):
            c.leggi_inizio(f"{DL}/x.zip", 100)


def test_leggi_inizio_con_waf_usa_la_riserva():
    def gestore(req):
        if req.headers["user-agent"] == UA_PROGETTO:
            return waf_html(req)
        return httpx.Response(206, content=b"PKzip")

    with client(gestore) as c:
        assert c.leggi_inizio(f"{DL}/x.zip", 2) == b"PK"
        assert c.user_agent_usato == UA_BROWSER


def test_chiusura_del_client():
    with client(ok_json) as c:
        assert not c._http.is_closed
    assert c._http.is_closed


def test_specchio_locale(tmp_path: Path):
    (tmp_path / "ckan").mkdir()
    (tmp_path / "ckan" / "cig-2025.json").write_text(
        json.dumps({"success": True, "result": PACCHETTO}), encoding="utf-8"
    )
    (tmp_path / "files" / "cig-2025").mkdir(parents=True)
    (tmp_path / "files" / "cig-2025" / "cig_csv_2025_01.zip").write_bytes(b"PKzip")
    s = SpecchioLocale(tmp_path)
    assert s.package_show("cig-2025")["name"] == "cig-2025"
    assert s.package_show("cig-2026") is None
    assert s.scarica(f"{DL}/cig_csv_2025_01.zip", tmp_path / "out.zip") == 5
    assert s.leggi_inizio(f"{DL}/cig_csv_2025_01.zip", 2) == b"PK"
    assert s.metadata_modificati() == {"cig-2025": "2026-01-23T08:20:09.269471"}

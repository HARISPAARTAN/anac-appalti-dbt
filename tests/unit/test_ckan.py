import json
from pathlib import Path

import httpx
import pytest

from anac_appalti.ckan import (
    ClientCkan,
    ErroreCkan,
    SpecchioLocale,
    WafRifiuto,
    rileva_waf,
    risorse_da_package,
)
from anac_appalti.config import UA_BROWSER, UA_PROGETTO

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

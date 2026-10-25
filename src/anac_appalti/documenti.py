"""Documenti generati: docs/ultima-esecuzione.md, blocchi numerici dei README, pagine del sito GitHub Pages."""

from __future__ import annotations

import re
from collections import Counter
from html import escape
from pathlib import Path

from anac_appalti.config import Impostazioni

MARCATORE_INIZIO = "<!-- numeri:inizio -->"
MARCATORE_FINE = "<!-- numeri:fine -->"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


def _intero(valore: int, lingua: str = "it") -> str:
    testo = f"{valore:,}"
    return testo.replace(",", ".") if lingua == "it" else testo


def _decimale(valore: float, cifre: int = 1, lingua: str = "it") -> str:
    testo = f"{valore:,.{cifre}f}"
    if lingua == "it":
        testo = testo.replace(",", "_").replace(".", ",").replace("_", ".")
    return testo


def _quota(parte: int, totale: int, lingua: str = "it") -> str:
    if not totale:
        return "–"
    valore = parte / totale * 100
    return f"{_decimale(valore, 2, lingua)} %" if lingua == "it" else f"{_decimale(valore, 2, lingua)}%"


def _durata(secondi: float) -> str:
    secondi = int(round(secondi))
    ore, resto = divmod(secondi, 3600)
    minuti, sec = divmod(resto, 60)
    if ore:
        return f"{ore} h {minuti} min"
    if minuti:
        return f"{minuti} min {sec} s"
    return f"{sec} s"


def _somma(sezione: dict, campo: str) -> float:
    return sum(float(v.get(campo, 0) or 0) for v in sezione.values())


def componi_ultima_esecuzione(record: dict) -> str:
    estrazione = record.get("estrazione", {})
    landing = record.get("landing", {})
    dbt = record.get("dbt", {})
    righe = [
        "# Ultima esecuzione",
        "",
        "Generato da `appalti report` dal log dell'ultima esecuzione.",
        "",
        "| Campo | Valore |",
        "|---|---|",
        f"| Esecuzione | `{record['run_id']}` |",
        f"| Versione | {record.get('versione', '')} (commit `{str(record.get('git_sha', ''))[:12]}`) |",
        f"| Inizio – fine | {record['inizio']} – {record['fine']} |",
        f"| Durata | {_durata(record.get('durata_s', 0))} |",
        f"| Esito | {record['esito']} |",
        f"| Anni in ambito | {', '.join(str(a) for a in record.get('anni', []))} |",
        f"| Data di riferimento | {record.get('data_riferimento', '')} |",
        "",
        "## Tempi per fase",
        "",
        "| Fase | Durata |",
        "|---|---|",
        f"| Estrazione | {_durata(_somma(estrazione, 'durata_s'))} |",
        f"| Landing | {_durata(_somma(landing, 'durata_s'))} |",
        f"| dbt build | {_durata(float(dbt.get('durata_s', 0) or 0))} |",
        f"| Totale | {_durata(record.get('durata_s', 0))} |",
        "",
        "## Estrazione",
        "",
        "| Tabella | File scaricati | Invariati | MB scaricati | User-Agent |",
        "|---|---:|---:|---:|---|",
    ]
    for tabella, dati in sorted(estrazione.items()):
        righe.append(
            f"| {tabella} | {dati.get('scaricati', 0)} | {dati.get('saltati', 0)} | "
            f"{_decimale(dati.get('byte', 0) / 1e6)} | {dati.get('user_agent', '')} |"
        )
    righe += ["", "## Landing", "", "| Tabella | File atterrati | Righe atterrate |", "|---|---:|---:|"]
    for tabella, dati in sorted(landing.items()):
        righe.append(
            f"| {tabella} | {dati.get('atterrati', 0)} | {_intero(sum((dati.get('righe') or {}).values()))} |"
        )
    esiti = dbt.get("esiti", {})
    righe += [
        "",
        "## dbt",
        "",
        f"Modelli: {dbt.get('n_modelli', 0)}; test (dati e unit): {dbt.get('n_test', 0)}.",
        "",
        "| Esito | Nodi |",
        "|---|---:|",
    ]
    righe += [f"| {esito} | {numero} |" for esito, numero in sorted(esiti.items())]
    if record.get("freschezza"):
        righe += ["", "## Freschezza delle sorgenti", "", "| Sorgente | Stato |", "|---|---|"]
        righe += [f"| {nome} | {stato} |" for nome, stato in sorted(record["freschezza"].items())]
    disco = record.get("disco", {})
    righe += [
        "",
        "## Disco e costi",
        "",
        "| Zona | GB |",
        "|---|---:|",
    ]
    righe += [f"| {zona} | {_decimale(byte / 1e9, 2)} |" for zona, byte in sorted(disco.items())]
    righe += ["", "Costo del warehouse: 0 EUR (DuckDB locale, nessun servizio a pagamento)."]
    if record.get("errori"):
        righe += ["", "## Errori", ""] + [f"- {errore}" for errore in record["errori"]]
    return "\n".join(righe) + "\n"


def scrivi_ultima_esecuzione(imp: Impostazioni, record: dict) -> Path:
    percorso = imp.docs / "ultima-esecuzione.md"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(componi_ultima_esecuzione(record), encoding="utf-8", newline="\n")
    return percorso


def gravita_test(manifest: dict, progetto: str = "anac_appalti") -> dict[str, int]:
    """Test dbt del progetto per gravità (error, warn) e numero di unit test, dal manifest."""
    conteggi = Counter(
        str(nodo.get("config", {}).get("severity", "error")).lower()
        for nodo in manifest["nodes"].values()
        if nodo["resource_type"] == "test" and nodo["package_name"] == progetto
    )
    unit = sum(1 for nodo in manifest.get("unit_tests", {}).values() if nodo.get("package_name") == progetto)
    return {"error": conteggi.get("error", 0), "warn": conteggi.get("warn", 0), "unit": unit}


def record_per_readme(registri: list[dict]) -> dict:
    """Base: l'ultima esecuzione riuscita con modelli dbt. Estrazione, landing e durata vengono dall'ultima
    esecuzione che ha scaricato file (la completa), anche se dopo è seguita una ricostruzione da archivio."""
    if not registri:
        raise ValueError("Nessun log di esecuzione")
    riusciti = [r for r in registri if r.get("esito") == "successo" and r.get("modelli")] or registri
    base = dict(riusciti[-1])
    con_download = [
        r for r in registri if any(v.get("scaricati", 0) for v in r.get("estrazione", {}).values())
    ]
    if con_download and con_download[-1]["run_id"] != base["run_id"]:
        completo = con_download[-1]
        base.update(
            estrazione=completo["estrazione"],
            landing=completo["landing"],
            durata_s=completo["durata_s"],
            esecuzione_download=completo["run_id"],
        )
    return base


def blocco_numeri(
    record: dict,
    indicatori: dict[str, int],
    quota_copertura: float,
    gravita: dict[str, int],
    lingua: str = "it",
) -> str:
    """Tabella delle misure dell'ultima esecuzione per i README (spec 1.4), in italiano o in inglese."""
    it = lingua == "it"
    i = indicatori
    lotti = i.get("lotti_correnti", 0)
    estrazione = record.get("estrazione", {})
    landing = record.get("landing", {})
    dbt = record.get("dbt", {})
    disco = record.get("disco", {})
    anni = record.get("anni", [])
    stati = Counter(record.get("freschezza", {}).values())
    righe_atterrate = sum(sum((v.get("righe") or {}).values()) for v in landing.values())

    def num(valore: float) -> str:
        return _intero(int(valore), lingua)

    def gb(byte: float) -> str:
        return f"{_decimale(byte / 1e9, 2, lingua)} GB"

    def con_quota(chiave: str, base: int) -> str:
        return f"{num(i.get(chiave, 0))} ({_quota(i.get(chiave, 0), base, lingua)})"

    freschezza = ", ".join(f"{s} {c}" for s, c in sorted(stati.items())) or (
        "non misurata" if it else "not measured"
    )
    durate = " · ".join(
        _durata(x)
        for x in (
            _somma(estrazione, "durata_s"),
            _somma(landing, "durata_s"),
            float(dbt.get("durata_s", 0) or 0),
            float(record.get("durata_s", 0) or 0),
        )
    )
    copertura = f"{quota_copertura * 100:.0f} %" if it else f"{quota_copertura * 100:.0f}%"
    misure = [
        ("Lotti (CIG) correnti", "Current lots (CIG)", num(lotti)),
        ("Anni di pubblicazione", "Publication years", f"{min(anni)}–{max(anni)}" if anni else "–"),
        (
            "File ANAC scaricati",
            "ANAC files downloaded",
            f"{num(_somma(estrazione, 'scaricati'))} ({gb(_somma(estrazione, 'byte'))})",
        ),
        ("Righe atterrate", "Rows landed", num(righe_atterrate)),
        (
            "Righe CIG → lotti correnti",
            "CIG rows → current lots",
            f"{num(i.get('righe_cig', 0))} → {num(lotti)}",
        ),
        (
            "Duplicati esatti rimossi",
            "Exact duplicates removed",
            con_quota("duplicati_esatti", i.get("righe_cig", 0)),
        ),
        ("Modelli dbt", "dbt models", num(dbt.get("n_modelli", 0))),
        (
            "Test dbt: gravità error / warn / unit test",
            "dbt tests: severity error / warn / unit tests",
            f"{gravita.get('error', 0)} / {gravita.get('warn', 0)} / {gravita.get('unit', 0)}",
        ),
        (
            "Esiti dell'ultimo dbt build",
            "Last dbt build results",
            ", ".join(f"{k} {v}" for k, v in sorted(dbt.get("esiti", {}).items())) or "–",
        ),
        ("Modelli con test sulla chiave", "Models with key tests", copertura),
        ("Lotti con date impossibili", "Lots with impossible dates", con_quota("date_impossibili", lotti)),
        (
            "Lotti con importi anomali (esclusi dalle somme)",
            "Lots with amount outliers (excluded from sums)",
            con_quota("importi_anomali", lotti),
        ),
        (
            "Righe di persone fisiche senza identità",
            "Natural-person rows without identity",
            num(i.get("righe_persone_fisiche", 0)),
        ),
        ("Freschezza delle sorgenti", "Source freshness", freschezza),
        ("Durata: estrazione · landing · dbt · totale", "Run time: extract · landing · dbt · total", durate),
        (
            "Disco: raw · landing · warehouse",
            "Disk: raw · landing · warehouse",
            " · ".join(gb(disco.get(z, 0)) for z in ("raw", "landing", "warehouse")),
        ),
        ("Costo del warehouse", "Warehouse cost", "0 EUR" if it else "EUR 0"),
    ]
    righe = ["| Misura | Valore |" if it else "| Measure | Value |", "|---|---:|"]
    righe += [f"| {m_it if it else m_en} | {valore} |" for m_it, m_en, valore in misure]
    mart = sorted(
        (chiave.removeprefix("radar."), dati["righe"])
        for chiave, dati in record.get("modelli", {}).items()
        if chiave.startswith("radar.")
    )
    if mart:
        righe += ["", "| Mart | Righe |" if it else "| Mart | Rows |", "|---|---:|"]
        righe += [f"| `{nome}` | {num(n)} |" for nome, n in mart]
    piede = (
        f"Data di riferimento {record.get('data_riferimento', '')}, esecuzione `{record['run_id']}`."
        if it
        else f"Reference date {record.get('data_riferimento', '')}, run `{record['run_id']}`."
    )
    if record.get("esecuzione_download"):
        piede += (
            f" Download, landing e durata totale dall'esecuzione `{record['esecuzione_download']}`."
            if it
            else f" Downloads, landing and total run time from run `{record['esecuzione_download']}`."
        )
    return "\n".join([*righe, "", piede])


def aggiorna_readme(percorso: Path, blocco: str) -> bool:
    testo = percorso.read_text(encoding="utf-8")
    modello = re.compile(re.escape(MARCATORE_INIZIO) + r"\n.*?\n" + re.escape(MARCATORE_FINE), re.DOTALL)
    if not modello.search(testo):
        raise ValueError(f"{percorso}: marcatori {MARCATORE_INIZIO} … {MARCATORE_FINE} assenti")
    nuovo = modello.sub(lambda _: f"{MARCATORE_INIZIO}\n{blocco}\n{MARCATORE_FINE}", testo, count=1)
    if nuovo == testo:
        return False
    percorso.write_text(nuovo, encoding="utf-8", newline="\n")
    return True


def _pagina(titolo: str, corpo: str, script: str = "") -> str:
    return (
        '<!doctype html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(titolo)}</title>\n"
        "<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;"
        "line-height:1.5;background:#fff;color:#1b1f24}a{color:#0b57d0}code{background:#f1f3f4;padding:0 .2rem}"
        "@media (prefers-color-scheme: dark){body{background:#0d1117;color:#e6edf3}a{color:#7cb7ff}"
        "code{background:#161b22}}</style>\n"
        f"</head>\n<body>\n{corpo}\n{script}</body>\n</html>\n"
    )


def componi_indice_sito(versione: str) -> str:
    corpo = (
        "<h1>anac-appalti-dbt</h1>\n"
        f"<p>Documentazione generata dalla CI sulla fixture sintetica (versione {escape(versione)}).</p>\n"
        '<ul>\n<li><a href="dbt/index.html">Documentazione dbt</a>: modelli, colonne, test, lineage.</li>\n'
        '<li><a href="dagster/index.html">Grafo degli asset Dagster</a>: estrazione, landing, dbt, qualità.</li>\n'
        '<li><a href="https://github.com/HARISPAARTAN/anac-appalti-dbt">Codice sorgente</a></li>\n</ul>\n'
        "<p>Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; "
        "dati elaborati. La fixture è sintetica e non contiene dati reali.</p>\n"
        '<p lang="en">English: dbt and Dagster documentation generated by CI from a synthetic fixture; no real '
        "data. Derived data is licensed CC BY-SA 4.0 (source: ANAC).</p>"
    )
    return _pagina("anac-appalti-dbt", corpo)


def _id_mermaid(chiave: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", chiave)


def componi_pagina_dagster(nodi: list[tuple[str, str, list[str]]]) -> str:
    gruppi: dict[str, list[str]] = {}
    for chiave, gruppo, _ in nodi:
        gruppi.setdefault(gruppo, []).append(chiave)
    linee = ["flowchart LR"]
    for gruppo, chiavi in sorted(gruppi.items()):
        linee.append(f"  subgraph {_id_mermaid(gruppo)} [{gruppo}]")
        linee += [f'    {_id_mermaid(c)}["{c}"]' for c in sorted(chiavi)]
        linee.append("  end")
    for chiave, _, dipendenze in sorted(nodi):
        linee += [f"  {_id_mermaid(d)} --> {_id_mermaid(chiave)}" for d in dipendenze]
    elenco = "\n".join(
        f"<li><code>{escape(c)}</code> ({escape(g)})"
        + (f" ← {', '.join(f'<code>{escape(d)}</code>' for d in dip)}" if dip else "")
        + "</li>"
        for c, g, dip in sorted(nodi)
    )
    corpo = (
        "<h1>Grafo degli asset Dagster</h1>\n"
        "<p>Asset definiti in <code>anac_appalti.definitions</code>: un asset raw e uno di landing per pacchetto "
        "ANAC, un asset per modello dbt, il riepilogo di qualità con il controllo <code>qualita_dati</code>. "
        "Job <code>pipeline_completo</code>, sensor <code>ckan_aggiornato</code>, schedule <code>mensile_25</code>.</p>\n"
        "<p>Il grafo viene dalle definizioni del codice e non dipende dai dati. La pagina è generata dalla CI "
        "sulla fixture sintetica, non da un'esecuzione sui dati reali: i numeri della prima esecuzione reale "
        "(2024–2026) sono nel README e in <code>docs/qualita-dati.md</code>.</p>\n"
        f'<pre class="mermaid">\n{escape(chr(10).join(linee))}\n</pre>\n'
        f"<h2>Elenco</h2>\n<ul>\n{elenco}\n</ul>\n"
        "<p>Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; "
        "dati elaborati.</p>"
    )
    script = (
        f'<script src="{MERMAID}"></script>\n'
        "<script>mermaid.initialize({startOnLoad:true, theme: window.matchMedia('(prefers-color-scheme: dark)')"
        ".matches ? 'dark' : 'default'});</script>\n"
    )
    return _pagina("Asset Dagster", corpo, script)

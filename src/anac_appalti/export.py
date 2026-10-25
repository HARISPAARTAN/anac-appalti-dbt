"""Esportazione dei nove mart Radar in Parquet con l'attribuzione CC BY-SA nei metadati del file.

`appalti export` esporta i nove file, li scansiona (codici fiscali personali e nomi di persona in ogni colonna di
testo, vedi `scansione_privacy`) e solo se la scansione è pulita scrive `ATTRIBUTION.md` e `SHA256SUMS`: la cartella
è quella da caricare nella release.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb

from anac_appalti.config import VERSIONE, Impostazioni

MART_RADAR: tuple[str, ...] = (
    "mart_appalti_regione_mese",
    "mart_appalti_settore_cpv",
    "mart_procedure",
    "mart_tasso_aggiudicazione",
    "mart_tempi_aggiudicazione",
    "mart_concorrenza",
    "mart_ribassi",
    "mart_varianti_subappalti",
    "mart_stazioni_appaltanti",
)
ATTRIBUZIONE = "Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati"


class ScansionePrivacyFallita(RuntimeError):
    """La scansione dei file esportati ha trovato un codice fiscale personale o un nome di persona."""


def esporta_mart(imp: Impostazioni, destinazione: Path | None = None) -> list[Path]:
    cartella = destinazione or imp.export
    cartella.mkdir(parents=True, exist_ok=True)
    metadati = (
        "{licenza: 'CC BY-SA 4.0', "
        f"attribuzione: '{ATTRIBUZIONE}', "
        "fonte: 'https://dati.anticorruzione.it/opendata', "
        "progetto: 'https://github.com/HARISPAARTAN/anac-appalti-dbt', "
        f"versione: '{VERSIONE}', data_riferimento: '{imp.data_riferimento}'}}"
    )
    scritti = []
    con = duckdb.connect(str(imp.warehouse_file), read_only=True)
    try:
        for mart in MART_RADAR:
            percorso = cartella / f"{mart}.parquet"
            destinazione_sql = percorso.as_posix().replace("'", "''")
            con.execute(
                f"COPY (SELECT * FROM radar.{mart} ORDER BY ALL) TO '{destinazione_sql}' "
                f"(FORMAT parquet, COMPRESSION zstd, KV_METADATA {metadati})"
            )
            scritti.append(percorso)
    finally:
        con.close()
    return scritti


def ultimo_mese(file: list[Path]) -> str | None:
    """Mese più recente (AAAA-MM) con lotti nel mart per regione e mese, o None se manca."""
    mart = next((p for p in file if p.stem == "mart_appalti_regione_mese"), None)
    if mart is None:
        return None
    con = duckdb.connect()
    try:
        valore = con.execute(f"select max(mese) from read_parquet('{mart.as_posix()}')").fetchone()[0]
    finally:
        con.close()
    return None if valore is None else f"{valore:%Y-%m}"


def mese_parziale(imp: Impostazioni, file: list[Path]) -> str | None:
    """Il mese più recente dei file se è anche il mese della data di riferimento: contiene solo i delta già usciti
    (nella prima esecuzione reale 2.183 lotti di ottobre 2026 contro circa 110.000 di un mese normale)."""
    mese = ultimo_mese(file)
    return mese if mese is not None and mese == imp.data_riferimento[:7] else None


def testo_attribuzione(imp: Impostazioni, run_id: str, mese_parziale: str | None) -> str:
    parziale_en = (
        f" The last month in the files ({mese_parziale}) is partial: it holds only the deltas published up to the"
        " reference date, far fewer lots than a normal month."
        if mese_parziale
        else ""
    )
    parziale_it = (
        f" L'ultimo mese nei file ({mese_parziale}) è parziale: contiene solo i delta pubblicati fino alla data di"
        " riferimento, molti meno lotti di un mese normale."
        if mese_parziale
        else ""
    )
    return f"""# Attribution / Attribuzione

{ATTRIBUZIONE}

- Data: nine aggregate marts derived from the ANAC open data (lots published 2024-2026), reference date
  {imp.data_riferimento}, run {run_id} of anac-appalti-dbt v{VERSIONE}. Aggregates only: no row-level data.{parziale_en}
- Natural persons: the files do not name natural persons. Contracting authorities that are sole traders or
  freelancers (individual legal form or a 16-character personal tax code) appear only as the single anonymous member
  "Persona fisica (identità non pubblicata)". The files were scanned, in every text column, for 16-character personal
  tax codes and for the names that match the personal tax codes of the ANAC register of contracting authorities
  (the scan is heuristic for names; the rule is applied upstream, in the dbt staging layer).
- Licence of the data: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0),
  https://creativecommons.org/licenses/by-sa/4.0/ . Derived works must carry the same licence and this attribution.
- Other sources: province names and codes of the ISTAT classification of the statistical units (ISTAT, CC BY 4.0);
  CPV division names from Regulation (EC) No 213/2008 (c) European Union, reuse with acknowledgement under
  Commission Decision 2011/833/EU; NUTS 2 codes from the Eurostat NUTS classification (c) European Union.
- Code: MIT, https://github.com/HARISPAARTAN/anac-appalti-dbt
- Integrity: see SHA256SUMS.

- Dati: nove mart aggregati elaborati dai dati aperti ANAC (lotti pubblicati 2024-2026), data di riferimento
  {imp.data_riferimento}, esecuzione {run_id}. Solo aggregati: nessun dato di dettaglio.{parziale_it}
- Persone fisiche: i file non nominano persone fisiche. Le stazioni appaltanti che sono ditte individuali o
  professionisti (forma giuridica individuale o codice fiscale personale di 16 caratteri) compaiono solo come
  l'unico membro anonimo "Persona fisica (identità non pubblicata)". I file sono stati scansionati, in ogni colonna di
  testo, per cercare codici fiscali personali di 16 caratteri e i nomi che corrispondono ai codici fiscali personali
  dell'anagrafe ANAC delle stazioni appaltanti (per i nomi la scansione è euristica; la regola è applicata a monte,
  nello staging dbt).
- Licenza dei dati: Creative Commons Attribuzione – Condividi allo stesso modo 4.0 Internazionale (CC BY-SA 4.0).
- Altre fonti: nomi e codici delle province dalla classificazione ISTAT delle unità statistiche (ISTAT, CC BY 4.0);
  nomi delle divisioni CPV dal Regolamento (CE) n. 213/2008 (c) Unione europea, riuso con citazione della fonte ai
  sensi della Decisione 2011/833/UE; codici NUTS 2 dalla classificazione NUTS di Eurostat (c) Unione europea.
- Codice: MIT.
"""


def scrivi_attribuzione(cartella: Path, imp: Impostazioni, run_id: str, mese_parziale: str | None) -> Path:
    percorso = cartella / "ATTRIBUTION.md"
    percorso.write_text(testo_attribuzione(imp, run_id, mese_parziale), encoding="utf-8", newline="\n")
    return percorso


def scrivi_somme(cartella: Path, file: list[Path]) -> Path:
    """SHA256SUMS nel formato di `sha256sum -b` (verificabile con `sha256sum -c SHA256SUMS`)."""
    righe = [f"{hashlib.sha256(p.read_bytes()).hexdigest()} *{p.name}" for p in file]
    percorso = cartella / "SHA256SUMS"
    percorso.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    return percorso


def esporta_per_release(imp: Impostazioni, run_id: str, destinazione: Path | None = None) -> list[Path]:
    """Esporta i nove mart, li scansiona e scrive ATTRIBUTION.md e SHA256SUMS. Alla prima segnalazione cancella i
    file esportati e solleva `ScansionePrivacyFallita`: una cartella con un rilievo non è mai pronta per la release."""
    from anac_appalti.scansione_privacy import scansiona_cartella

    cartella = destinazione or imp.export
    file = esporta_mart(imp, cartella)
    rilievi, _ = scansiona_cartella(imp, cartella)
    if rilievi:
        for percorso in file:
            percorso.unlink(missing_ok=True)
        dettaglio = "; ".join(f"{r} ({r.valore!r})" for r in rilievi[:5])
        raise ScansionePrivacyFallita(f"{len(rilievi)} rilievi nei file esportati, per esempio: {dettaglio}")
    scrivi_attribuzione(cartella, imp, run_id, mese_parziale(imp, file))
    scrivi_somme(cartella, file)
    return file

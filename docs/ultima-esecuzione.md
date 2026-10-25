# Ultima esecuzione

Generato da `appalti report` dal log dell'ultima esecuzione.

| Campo | Valore |
|---|---|
| Esecuzione | `20261025T160014-be23e3` |
| Versione | 0.1.1 (commit `e76ea81e48f9`, albero di lavoro pulito) |
| Strumenti | dagster 1.13.26, dagster-dbt 0.29.26, dbt-core 1.12.6, dbt-duckdb 1.11.0, duckdb 1.5.6, python 3.13.11 |
| Inizio – fine | 2026-10-25T16:00:14 – 2026-10-25T16:15:17 |
| Durata | 15 min 3 s |
| Esito | successo |
| Anni in ambito | 2024, 2025, 2026 |
| Data di riferimento | 2026-10-25 |

## Tempi per fase

| Fase | Durata |
|---|---|
| Estrazione | 7 min 13 s |
| Landing | 2 min 5 s |
| dbt build | 5 min 32 s |
| Totale | 15 min 3 s |

## Estrazione

| Tabella | File scaricati | Invariati | MB scaricati | User-Agent |
|---|---:|---:|---:|---|
| aggiudicatari | 9 | 0 | 211,6 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| aggiudicazioni | 9 | 0 | 195,2 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| cig | 34 | 0 | 1.198,5 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| partecipanti | 9 | 0 | 277,5 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| stazioni_appaltanti | 2 | 0 | 3,1 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| subappalti | 9 | 0 | 39,0 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| tipi_scelta_contraente | 2 | 0 | 0,0 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |
| varianti | 9 | 0 | 14,8 | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 |

## Landing

| Tabella | File atterrati | Righe atterrate |
|---|---:|---:|
| aggiudicatari | 8 | 7.699.833 |
| aggiudicazioni | 8 | 6.580.581 |
| cig | 31 | 6.334.426 |
| partecipanti | 8 | 13.130.584 |
| stazioni_appaltanti | 1 | 48.040 |
| subappalti | 8 | 509.650 |
| tipi_scelta_contraente | 1 | 47 |
| varianti | 8 | 416.997 |

## dbt

Modelli: 42; test (dati e unit): 192.

| Esito | Nodi |
|---|---:|
| pass | 183 |
| success | 47 |
| warn | 9 |

## Freschezza delle sorgenti

| Sorgente | Stato |
|---|---|
| anac.aggiudicatari | pass |
| anac.aggiudicazioni | pass |
| anac.cig | pass |
| anac.partecipanti | pass |
| anac.subappalti | pass |
| anac.varianti | pass |

## Disco e costi

| Zona | GB |
|---|---:|
| landing | 1,90 |
| raw | 1,94 |
| warehouse | 5,72 |

Costo del warehouse: 0 EUR (DuckDB locale, nessun servizio a pagamento).

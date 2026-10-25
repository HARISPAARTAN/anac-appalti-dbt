# Ultima esecuzione

Generato da `appalti report` dal log dell'ultima esecuzione.

| Campo | Valore |
|---|---|
| Esecuzione | `20261025T125951-e7d029` |
| Versione | 0.1.0 (commit `11b54f2f7977`) |
| Inizio – fine | 2026-10-25T12:59:51 – 2026-10-25T13:11:58 |
| Durata | 12 min 7 s |
| Esito | successo |
| Anni in ambito | 2024, 2025, 2026 |
| Data di riferimento | 2026-10-25 |

## Tempi per fase

| Fase | Durata |
|---|---|
| Estrazione | 0 s |
| Landing | 2 min 57 s |
| dbt build | 8 min 43 s |
| Totale | 12 min 7 s |

## Estrazione

| Tabella | File scaricati | Invariati | MB scaricati | User-Agent |
|---|---:|---:|---:|---|

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

Modelli: 40; test (dati e unit): 171.

| Esito | Nodi |
|---|---:|
| pass | 164 |
| success | 43 |
| warn | 7 |

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
| warehouse | 8,77 |

Costo del warehouse: 0 EUR (DuckDB locale, nessun servizio a pagamento).

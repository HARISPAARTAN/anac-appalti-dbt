# ADR-001: DuckDB e dbt-core come motore di trasformazione

Stato: accettata (2026-10-25)

## Contesto

Il progetto deve mostrare un livello di analytics engineering completo (modelli, test, documentazione, lineage)
su alcuni milioni di righe (stima), senza budget per un warehouse in cloud e senza segreti in CI. La stessa pipeline deve
girare sul portatile del proprietario e su un runner GitHub Actions.

## Decisione

dbt-core con l'adapter dbt-duckdb su un unico file DuckDB (`data/warehouse/appalti.duckdb`). I modelli leggono il
Parquet di landing con `read_parquet`; le versioni sono fissate (`dbt-core` 1.12, `dbt-duckdb` 1.11,
`duckdb` < 2, blocco esatto in `uv.lock`). La CI usa lo stesso motore sulla fixture sintetica.

MotherDuck non entra nella v1: nessun target cloud, nessun account, nessun segreto. Il profilo dbt ha solo i
target `locale` (dati reali) e `ci` (fixture).

## Alternative scartate

- Snowflake o BigQuery in prova gratuita: richiedono account, segreti e scadenze, contro le regole del progetto.
- Trasformazioni in pandas o SQL senza dbt: niente test dichiarativi, niente documentazione e lineage generati,
  e proprio dbt è la competenza da dimostrare.
- MotherDuck: non necessario per un progetto su una sola macchina (decisione del proprietario per la v1; si
  riconsidera solo se un annuncio di lavoro lo chiede).

## Conseguenze

- Costo del warehouse 0 EUR; un'esecuzione completa resta locale e riproducibile.
- Il file DuckDB ammette un solo processo in scrittura: dbt gira come sottoprocesso e la pipeline non apre
  connessioni concorrenti durante `dbt build`. Per lo stesso motivo il job Dagster usa l'esecutore in processo
  (vedi ADR-002).
- Il tipo `decimal(18,2)` degli importi e le funzioni di data e di testo sono quelli di DuckDB: una futura
  migrazione verso un warehouse in cloud cambia profilo e qualche funzione SQL, non la struttura dei modelli.

# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [Non rilasciato]

- Struttura del progetto, configurazione, CI.
- Archivio raw append-only con manifest SHA-256, landing in Parquet con allowlist dei contratti, riconciliazione delle righe e privacy applicata al landing, fixture sintetica di due mesi.
- Correzioni dopo la review del Task 3: SHA-256 verificato a ogni lettura e prima di cancellare un download; impronta di riga con ordinale per le righe con identità annullata (nessun surrogato per persona) e colonne `_classe_cf`; differenze di riconciliazione e righe scartate segnalate (comando `appalti landing` con codice di uscita 1); limiti DuckDB in `appalti.toml`; test di integrazione in CI.
- Progetto dbt: sources generati dai contratti, staging tipizzato con regola persone fisiche (seconda linea sopra il landing, classe conservata da `_classe_cf`), livello intermedio versionato (versioni, correnti, operatori, flag di qualità, riconciliazione), seed, unit test dbt e ponte Python `pipeline.py` che esegue dbt in un sottoprocesso.

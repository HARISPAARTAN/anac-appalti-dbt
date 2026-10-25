# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [Non rilasciato]

La v0.1.0 esce dopo la prima esecuzione completa sui dati reali 2024–2026, che non è ancora stata fatta: finora
ogni misura viene dalla fixture sintetica.

### Aggiunto

- Estrazione incrementale dal portale CKAN di ANAC con riconoscimento del WAF dal corpo della risposta e
  User-Agent di riserva da browser, registrato nel log.
- Archivio raw append-only con manifest SHA-256 e procedura `--da-archivio` per i file scaricati a mano;
  intestazioni reali dei CSV lette dal portale (`appalti intestazioni`).
- Landing in Parquet con contratti di sorgente, allowlist delle colonne, controllo dello schema,
  riconciliazione con i logCsv di ANAC e annullamento delle persone fisiche prima della scrittura (ordinale di
  riga per l'identità di riga, nessun abbinamento tra file).
- Progetto dbt su DuckDB: 8 modelli di staging, 12 intermedi, schema a stella con 6 dimensioni e 5 fatti,
  9 mart Radar con contratto applicato; 40 modelli in tutto.
- Test dbt sulle chiavi di ogni modello (copertura verificata da `appalti copertura-test`), controlli di qualità
  con gravità avviso, unit test dbt, test di privacy, regola unica del punto decimale e test `perdita_parsing`.
- Report di qualità (`docs/qualita-dati.md`), log di esecuzione e impronte per modello.
- Orchestrazione Dagster: asset per pacchetto e per modello, controllo `qualita_dati`, sensor giornaliero e
  schedule mensile (spenti per default); `appalti run`, `report`, `export`, `copertura-test` e `docs`.
- Esportazione dei mart in Parquet con attribuzione CC BY-SA 4.0 nei metadati.
- CI su GitHub Actions con fixture sintetica (due mesi, idempotenza) e documentazione dbt e grafo Dagster su
  GitHub Pages.
- README in italiano e in inglese con i segnaposto dei numeri (`<!-- numeri:inizio -->`), cinque ADR, glossario
  italiano, inglese e tedesco.

### Corretto

- Un errore di landing o di dbt fa fallire l'asset Dagster: lo stato dell'esecuzione di schedule, sensor e
  interfaccia non è più verde quando la pipeline fallisce, non solo l'uscita di `appalti run`.
- Il job `pipeline_completo` usa l'esecutore in processo (nessun download parallelo, nessun aggiornamento perso
  del registro di landing).
- `docs/qualita-dati.md` generato sulla fixture dice di esserlo (titolo, primo paragrafo e riga "Generato da").
- Test dei percorsi di fallimento, del contenuto del log di esecuzione, dello stato spento di schedule e sensor,
  delle dipendenze degli asset e dei comandi `run`, `report`, `export` e `docs`.

### Da confermare sul primo file reale

- L'assunzione `cod_esito = 1` per un'aggiudicazione (`flag_esito_aggiudicato`).
- La regola del punto singolo come separatore decimale di importi e ribassi.

# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [0.1.1] - 2026-10-25

Correzioni dalla revisione della 0.1.0.

### Aggiunto

- Riconciliazione fisica: per i file senza conteggio nel logCsv (i `cig-AAAA`) il landing conta i record fuori dalle
  virgolette del CSV e registra `ok_fisico` o `differenza_fisica` (`differenza_fisica` fa fallire il test dbt
  `assert_riconciliazione`). Misurato sull'archivio della 0.1.0: tutti i 24 file annuali coincidono (2.704.490 righe).
- Test che fissano il comportamento del lettore con `escape = '\'` (backslash isolato eliminato, coppia `\\` letta
  come un backslash) e test del conteggio fisico.

### Corretto

- `appalti report` scrive ogni numero dei README da una sola esecuzione (l'ultima riuscita) e dichiara "non
  disponibile in questa esecuzione" una fase assente: righe atterrate 34.720.158 e riga delle durate coerente
  (prima mescolava due esecuzioni).
- Seed delle province: descrizione corretta (classificazione 2021 più i codici sardi 112-119); sigla vuota per i
  codici 113 e 119, senza sigla ufficiale.
- Il filtro `filterwarnings` toglie dall'output dei test solo l'avviso di deprecazione di `sqlglotrs`.

## [0.1.0] - 2026-10-25

Prima versione, misurata sulla prima esecuzione completa sui dati reali 2024–2026 (run `20261025T125951-e7d029`):
3.734.851 lotti, 3.508.850 aggiudicazioni collegate ai lotti, 4.828.798 partecipazioni. I nove mart aggregati sono
negli asset della release.

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
- README in italiano e in inglese con i numeri misurati (`<!-- numeri:inizio -->`), cinque ADR, glossario
  italiano, inglese e tedesco.

### Corretto

- Un errore di landing o di dbt fa fallire l'asset Dagster: lo stato dell'esecuzione di schedule, sensor e
  interfaccia non è più verde quando la pipeline fallisce, non solo l'uscita di `appalti run`.
- Il job `pipeline_completo` usa l'esecutore in processo (nessun download parallelo, nessun aggiornamento perso
  del registro di landing).
- `docs/qualita-dati.md` generato sulla fixture dice di esserlo (titolo, primo paragrafo e riga "Generato da").
- Test dei percorsi di fallimento, del contenuto del log di esecuzione, dello stato spento di schedule e sensor,
  delle dipendenze degli asset e dei comandi `run`, `report`, `export` e `docs`.

- Il landing legge i CSV ANAC con il backslash come carattere di escape: le virgolette dentro un valore sono scritte
  come `\"` e il lettore a virgolette raddoppiate perdeva da 19 a 1.335 righe in 13 file (trovato dalla
  riconciliazione con i logCsv).
- La denominazione che è un codice fiscale personale (ditte individuali con partita IVA) è annullata al landing e
  in staging; il test sui mart non trova più codici personali.
- Otto codici provincia della Sardegna (112–119) aggiunti al seed; il territorio `ND` scende all'1,6 % dei lotti.

### Verificato sul primo file reale

- `cod_esito = 1` vale `AGGIUDICATA` (99,51 % delle aggiudicazioni correnti): l'assunzione resta.
- La regola del punto singolo come separatore decimale di importi e ribassi regge su 3,7 milioni di importi.
- Perdite di lettura zero; riconciliazione con i logCsv senza differenze; il WAF rifiuta lo User-Agent del progetto
  e accetta quello da browser.

# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [0.1.1] - 2026-10-25

Correzioni dalla revisione finale della 0.1.0, misurate sull'esecuzione completa da zero `20261025T160014-be23e3` (15 min 3 s:
download di 83 file e 1,94 GB, landing, `dbt build`, export). Il mart delle stazioni appaltanti della 0.1.0 nominava
persone fisiche ed è stato ritirato dalla release 0.1.0: la 0.1.1 lo sostituisce.

### Sicurezza e privacy

- Le stazioni appaltanti che sono persone fisiche (codice fiscale di 16 caratteri o forma giuridica individuale) non
  hanno più nome, codice fiscale, partita IVA né codice AUSA nei mart: staging annulla i valori, anche sui lotti e per
  le amministrazioni assenti dall'anagrafe, e `int_stazioni` le riduce alla chiave `PERSONA_FISICA` (401 stazioni:
  399 dell'anagrafe e 2 viste solo nei lotti). Due seed di codici AUSA opachi, mai nomi, coprono la classe che le regole
  non vedono (nome di persona, codice segnaposto, forma giuridica non classificata): `ausa_persone_fisiche` (18 persone,
  una trovata dalla scansione di export, 17 dalla revisione dei candidati) e `ausa_enti_verificati` (40 enti).
- Revisione dei candidati: `int_stazioni_da_verificare` elenca le stazioni con codice non di 11 cifre, forma giuridica
  non classificata o assente e nome di 2-3 parole senza parole di ente (57 la prima volta: 17 persone, 40 enti); il test
  `assert_candidati_stazioni_classificati` fallisce finché ognuna non è in uno dei due seed. Il nome si legge solo in
  locale; nel dubbio è una persona.
- Test nuovo per join sulla sorgente (`assert_nessuna_stazione_personale_nei_mart`), controllo dei 16 caratteri anche
  sulla dimensione, test unitari e di integrazione con stazioni che sono persone fisiche.
- `appalti export` scansiona ogni colonna di testo dei nove Parquet (codici fiscali personali e nomi che
  corrispondono ai codici personali dell'anagrafe), cancella i file se trova qualcosa e solo altrimenti scrive
  `ATTRIBUTION.md` e `SHA256SUMS`.
- Testo libero: i codici fiscali personali in `oggetto_gara`, `oggetto_lotto`, `motivo_cancellazione`, `oggetto` dei
  subappalti e `motivo_variante` sono sostituiti da `[CF]` al landing (794 sostituzioni), contati nel registro, nel
  log e nel report.
- Ditte individuali tra gli operatori (decisione del proprietario, reversibile): nome annullato in staging e in
  `dim_operatori` (12.424 operatori), codice di 11 cifre tenuto come chiave locale non pubblicata.
- ADR-004, `data/LICENSE-DATA.md` e i README dichiarano il perimetro reale della privacy, con i numeri misurati: il
  landing delle stazioni conserva 361 codici personali, quello dei lotti 91 righe (11 codici), e il landing degli
  operatori i nomi delle ditte individuali; i nomi nel testo libero non sono riconosciuti.

### Aggiunto

- Riconciliazione fisica: per i file senza conteggio nel logCsv (i `cig-AAAA`) il landing conta i record fuori dalle
  virgolette del CSV e registra `ok_fisico` o `differenza_fisica` (`differenza_fisica` fa fallire il test dbt
  `assert_riconciliazione`). Nell'esecuzione `20261025T160014-be23e3`: 73 file, 49 `ok`, 24 `ok_fisico` (2.704.490 righe), nessuna
  differenza.
- Test di avviso `dq_subappalti_collassati` e `dq_varianti_collassate`: contano le righe con lo stesso id scartate da
  `int_subappalti__corrente` e `int_varianti__corrente` (13.826 e 18.378 righe; la correzione strutturale è in
  roadmap per la 0.2.0).
- Il log di esecuzione registra se l'albero di git è modificato e le versioni di Python, dbt-core, dbt-duckdb,
  DuckDB, Dagster e dagster-dbt; il report e il README mostrano stazioni anonimizzate, ditte individuali e codici
  mascherati.
- Test che fissano il comportamento del lettore con `escape = '\'` (backslash isolato eliminato, coppia `\\` letta
  come un backslash), test del conteggio fisico e test di coerenza della versione nei quattro posti e nel CHANGELOG.

### Modificato

- `dim_stazioni_appaltanti` ha il membro `PERSONA_FISICA`; il mart ha 71.971 righe (71.987 nella 0.1.0). Nuovi
  modelli `int_stazioni` e `int_stazioni_da_verificare` (42 modelli); tie-break su `_hash_riga` nella scelta della riga dell'anagrafe.
- `appalti report` scrive ogni numero dei README da una sola esecuzione (l'ultima riuscita) e dichiara "non
  disponibile in questa esecuzione" una fase assente.
- README: tabella dei mart con granularità e base, diagramma ER dichiarato semplificato, "offline" e "ogni
  esecuzione lascia un report" corretti, ultimo mese (2026-10, 2.183 lotti) dichiarato parziale anche in
  `ATTRIBUTION.md`, frase sulle date impossibili con le misure (97,7 % affidamenti diretti, 85,6 % scadenza prima
  della pubblicazione), frase sui backslash corretta (2.120 byte: 1.726 in 863 coppie più 394 virgolette protette).
- Attribuzione di ISTAT (province), CPV (Reg. CE 213/2008) e NUTS (Eurostat) in `data/LICENSE-DATA.md`,
  `ATTRIBUTION.md` e README; licenza MIT dichiarata per la fixture sintetica.
- Versione 0.1.1. Il filtro `filterwarnings` toglie dall'output dei test l'avviso di `sqlglotrs` e quello di
  `AssetExecutionContext.op` che nasce dentro `dagster_dbt/asset_utils.py`.
- Chi aggiorna un warehouse esistente deve rieseguire `dbt build --full-refresh` (nuove colonne in
  `int_cig__corrente` e nel registro di atterraggio).

### Corretto

- Seed delle province: descrizione corretta (classificazione 2021 più i codici sardi 112-119); sigla vuota per i
  codici 113 e 119, senza sigla ufficiale.
- ADR-003: la dimensione dell'archivio è misurata (1,94 GB), non più da misurare.

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

# Licenza dei dati

Il codice di questo repository è rilasciato con licenza MIT (vedi `LICENSE`).

I dati derivati pubblicati dal repository (i mart aggregati, solo negli asset delle release)
sono elaborazioni dei dati aperti ANAC e sono rilasciati con la stessa licenza della fonte,
Creative Commons Attribuzione – Condividi allo stesso modo 4.0 Internazionale (CC BY-SA 4.0,
https://creativecommons.org/licenses/by-sa/4.0/deed.it).

Attribuzione richiesta:

Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati

La fixture in `data/fixtures/` è sintetica: è generata da `appalti fixture genera`, non contiene dati ANAC
reali né dati di persone fisiche ed è rilasciata con la stessa licenza MIT del codice (non è un dato derivato
ANAC, quindi non ha l'obbligo di attribuzione né di condivisione allo stesso modo).

## Altre fonti nei dati derivati

I mart contengono anche dati di riferimento di terzi, letti da `dbt/seeds/`: i nomi e i codici delle province dalla
classificazione ISTAT delle unità statistiche (ISTAT, licenza CC BY 4.0, seed `regioni_province`); i nomi delle
divisioni CPV dal Regolamento (CE) n. 213/2008 sul vocabolario comune per gli appalti (© Unione europea, riuso con
citazione della fonte ai sensi della Decisione 2011/833/UE, seed `divisioni_cpv`); i codici NUTS 2 dalla
classificazione NUTS di Eurostat (© Unione europea). Compaiono nelle colonne `regione`, `nuts2` e
`descrizione_divisione`. La citazione è anche in `ATTRIBUTION.md`, che accompagna ogni release.

## English

Code is MIT. Derived data (aggregate marts, only in release assets) is processed ANAC open
data and is released under CC BY-SA 4.0 with the attribution above. The marts also carry third-party reference
data from `dbt/seeds/`: ISTAT province names and codes (CC BY 4.0), CPV division names from Regulation (EC)
No 213/2008 (c) European Union, reused with acknowledgement under Decision 2011/833/EU, and NUTS 2 codes from
Eurostat's NUTS classification (c) European Union; the acknowledgement is also in `ATTRIBUTION.md`. The fixture in
`data/fixtures/` is synthetic, contains no real ANAC records and no personal data, and is released under the same
MIT licence as the code.

## Dati personali: cosa si pubblica e cosa resta in locale

**Nei file pubblicati** (i nove mart aggregati delle release, il repository, la documentazione) non compare nessuna
persona fisica individuata dalle regole del codice fiscale, della forma giuridica e della revisione manuale:
`appalti export` scansiona ogni colonna di testo dei Parquet alla ricerca di codici fiscali personali e di nomi che
corrispondono ai codici personali dell'anagrafe delle stazioni appaltanti e, se trova qualcosa, non scrive i file. Le
stazioni appaltanti che sono persone fisiche sono un solo membro anonimo. Il controllo dei nomi è euristico e la
revisione manuale copre i nomi di 2-3 parole delle voci non classificate dell'anagrafe: una persona fuori da queste
regole non si può escludere.

**In locale** (archivio raw, landing, warehouse: non pubblicati) la protezione ha un perimetro, descritto per
colonne e misurato (dettaglio e numeri in `docs/decisioni/ADR-004-privacy.md`):

- L'archivio raw (`data/raw/`, non versionato) conserva i file ANAC scaricati così come sono: è la copia storica,
  perché ANAC rimuove i delta superati.
- Il landing in Parquet (`data/landing/`) di `aggiudicatari`, `partecipanti` e `subappalti` non contiene codici
  fiscali di persone fisiche né le denominazioni delle righe con codice personale: prima di scrivere ogni Parquet,
  `appalti` passa le colonne `dato_personale` dei contratti (`codice_fiscale`, `denominazione`, `cf_subappaltante`)
  dal classificatore dei codici fiscali. Il codice fiscale resta solo se è una partita IVA di 11 cifre; la
  denominazione solo se il codice fiscale della stessa riga lo è; negli altri casi (16 caratteri di persona fisica,
  valori non verificabili, assenti) il valore è NULL. Anche l'impronta di riga `_hash_riga` è calcolata sui valori
  già ripuliti. Non esiste nessun identificativo stabile per persona (nemmeno un hash con sale: l'hash di un codice
  fiscale personale resta un identificativo personale). Il landing conserva invece la classe del codice fiscale
  (`_classe_cf`: persona_giuridica, persona_fisica, non_verificabile, assente; `_classe_cf_subappaltante` per i
  subappalti) e la posizione della riga nel file (`_ordinale_riga`), che entra nell'impronta delle sole righe in cui
  un identificativo è stato annullato: persone fisiche diverse nello stesso file restano righe diverse, e il
  conteggio dei partecipanti si basa su questo. Le persone fisiche non sono mai abbinate tra file diversi, due righe
  identiche di persone fisiche non sono riconosciute come duplicati esatti, e le righe annullate formano il gruppo
  "persona fisica / non identificata", che non si collega a nessuna dimensione degli operatori.
- **Non coperti dal landing, misurati nell'esecuzione 20261025T151521-610332**: l'anagrafe `stazioni_appaltanti` conserva
  361 codici fiscali personali con i nomi come ANAC li pubblica; il landing dei lotti conserva
  91 righe (11 codici) con il codice fiscale personale dell'amministrazione
  appaltante; il nome delle ditte individuali con partita IVA resta nel landing degli operatori. Lo staging dbt
  annulla questi valori (stazioni appaltanti che sono persone fisiche, ditte individuali) e ripete l'annullamento
  degli operatori una seconda volta.
- **Testo libero**: nelle colonne `oggetto_gara`, `oggetto_lotto`, `motivo_cancellazione`, `oggetto` (subappalti) e
  `motivo_variante` i codici fiscali personali di 16 caratteri sono sostituiti da `[CF]` al landing (794
  sostituzioni nell'esecuzione 20261025T151521-610332). I nomi di persona nel testo libero non sono riconosciuti.
- Nei pacchetti in ambito non esiste una colonna RUP.

### English

**In the published files** (the nine aggregate marts in the releases, the repository, the documentation) no
natural person identified by the tax-code, legal-form or manual-review rules appears: `appalti export` scans every
text column of the Parquet files for personal tax codes and for names that match the personal codes of the
contracting-authority register, and writes nothing if it finds any. Contracting authorities that are natural persons
are one anonymous member. The name check is a heuristic and the manual review covers the 2-3 word names of the
register's unclassified entries: a person outside those rules cannot be excluded.

**Locally** (raw archive, landing zone, warehouse: never published) protection has a scope, stated per column and
measured (details and numbers in `docs/decisioni/ADR-004-privacy.md`, written in Italian):

- The raw archive (`data/raw/`, git-ignored) keeps the downloaded ANAC files untouched, as the only historical copy.
- The Parquet landing zone (`data/landing/`) of `aggiudicatari`, `partecipanti` and `subappalti` holds no personal
  tax codes and no names on rows with a personal code: before each Parquet is written, the contract columns
  flagged `dato_personale` go through the tax-code classifier. A tax code is kept only if it is an 11-digit VAT
  number; the name is kept only if the same row's tax code is; otherwise the value is NULL. The row hash
  `_hash_riga` is computed on the already cleaned values. There is no stable per-person identifier of any kind (not
  even a salted hash: a hash of a personal tax code is still a personal identifier). The landing zone keeps the
  tax-code class (`_classe_cf`: persona_giuridica, persona_fisica, non_verificabile, assente;
  `_classe_cf_subappaltante` for subcontracts) and the row position in the file (`_ordinale_riga`), which enters the
  row hash only for rows where an identifier was blanked: distinct natural persons in one file stay distinct rows,
  and participant counts rely on this. Natural persons are never matched across files, identical rows of natural
  persons are not recognised as exact duplicates, and blanked rows form a "natural person / not identified" bucket
  that cannot be joined to an operator dimension.
- **Not covered by the landing zone, measured in run 20261025T151521-610332**: the `stazioni_appaltanti` register keeps
  361 personal tax codes with names as ANAC publishes them; the lots landing zone keeps
  91 rows (11 codes) with the personal tax code of the contracting authority; the
  name of sole traders with a VAT number stays in the operators' landing zone. dbt staging blanks these values
  (contracting authorities that are natural persons, sole traders) and repeats the operators' blanking a second
  time.
- **Free text**: in the columns `oggetto_gara`, `oggetto_lotto`, `motivo_cancellazione`, `oggetto` (subcontracts)
  and `motivo_variante`, personal tax codes of 16 characters are replaced by `[CF]` at landing (794
  replacements in run 20261025T151521-610332). Personal names in free text are not recognised.
- No in-scope package has a RUP column.

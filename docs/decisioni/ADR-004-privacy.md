# ADR-004: Privacy: le persone fisiche non vengono mai identificate

Stato: accettata (2026-10-25)

## Contesto

I file `aggiudicatari`, `partecipanti` e `subappalti` contengono anche persone fisiche (ditte individuali e
professionisti), con codice fiscale di 16 caratteri e nome completo: circa il 10 % delle righe in un campione dei
file reali. Il progetto è pubblico e non deve diffondere né ricostruire dati personali oltre ciò che serve alle
analisi aggregate. Nei pacchetti in ambito non esiste una colonna RUP o con nomi di responsabili.

## Decisione

La privacy si ottiene non avendo mai l'identità a valle del download, non nascondendola dopo.

1. **Annullamento al landing.** La landing tiene solo le colonne del contratto marcate `tenere: true`. Prima di
   scrivere ogni Parquet, le colonne `dato_personale: true` (`codice_fiscale`, `denominazione`,
   `cf_subappaltante`) passano dal classificatore dei codici fiscali: 11 cifre `persona_giuridica`, 16 caratteri
   secondo lo schema del codice personale `persona_fisica`, altro `non_verificabile`, vuoto `assente`. Codice e
   denominazione restano solo per `persona_giuridica`; negli altri casi diventano NULL. Il Parquet non contiene
   mai l'identità di una persona fisica.
2. **Nessun identificativo stabile.** Non si calcola nessun pseudonimo, nemmeno un hash con sale: l'hash di un
   codice fiscale personale resta un identificativo personale. La landing conserva soltanto la classe del codice
   (`_classe_cf`, `_classe_cf_subappaltante`) e la posizione della riga nel file (`_ordinale_riga`).
3. **Identità di riga con l'ordinale.** L'impronta di riga `_hash_riga` è calcolata sui valori già ripuliti e,
   solo per le righe in cui un identificativo è stato annullato, include l'ordinale di riga: persone fisiche
   diverse nello stesso file restano righe diverse e i partecipanti si contano correttamente. L'ordinale vale
   solo dentro un file e non viene mai confrontato tra file.
4. **Mai abbinate tra file.** Una persona fisica non viene riconosciuta in un altro file o in un'altra
   versione. Due righe identiche di persone fisiche non sono "duplicati esatti"; le righe annullate formano il
   gruppo "persona fisica / non identificata" e non si collegano a nessuna dimensione degli operatori.
5. **Seconda linea di difesa in staging.** Lo staging classifica di nuovo il codice ancora presente
   (`classifica_cf`) e usa la classe del landing solo quando il codice è già NULL (`classe_privacy`): se un
   codice personale arrivasse comunque in staging, verrebbe annullato lì. La classe (`tipo_soggetto_privacy`) serve
   a contare e a spiegare i NULL, mai a ricostruire l'identità.
6. **Nel core, un unico operatore.** `dim_operatori` contiene le persone giuridiche e due membri anonimi,
   `PERSONA_FISICA` e `NON_VERIFICABILE`. In `fct_partecipazioni` tutte le persone fisiche dello stesso lotto e
   ruolo confluiscono nella riga di `PERSONA_FISICA` (chiave CIG × operatore × ruolo) e il loro numero resta
   in `n_righe_partecipanti` e `n_righe_aggiudicatari`.
7. **Prove.** Test dbt verificano che nessun mart contenga codici fiscali personali
   (`assert_nessun_cf_personale_nei_mart`) e che nessuna colonna di staging, intermediate, core o radar si chiami come un dato
   personale (token `rup`, `nome`, `cognome`, `responsabile`: `assert_nessuna_colonna_personale`). Unit test dbt
   coprono la seconda linea di difesa di partecipanti e subappalti. Il classificatore Python e la macro SQL
   hanno gli stessi modelli e un test li confronta. Un test unitario cerca codici fiscali personali in tutti i
   documenti Markdown; la fixture è sintetica e non contiene persone fisiche.
8. **Perimetro.** L'archivio raw (`data/raw/`) conserva i file ANAC originali, compresi i dati personali, perché
   è l'unica copia storica dei delta superati; resta locale e fuori da git (vedi ADR-003). Il sito di
   documentazione è generato sulla fixture sintetica.

## Alternative scartate

- Pseudonimo HMAC del codice fiscale: resta un dato personale, richiede un segreto e aggiunge poco a mart
  aggregati.
- Annullare le identità solo in staging: il Parquet di landing conterrebbe dati personali in chiaro, con una
  superficie di esposizione molto più ampia.
- Escludere del tutto le righe delle persone fisiche: falserebbe i conteggi di partecipanti e aggiudicatari.
- Collassare le persone fisiche in una sola riga già al landing: l'impronta di riga non distinguerebbe più i
  partecipanti e il conteggio andrebbe perso.

## Conseguenze

- Le analisi per operatore non distinguono tra persone fisiche diverse e non seguono una persona nel tempo.
- Le ditte individuali con partita IVA di 11 cifre restano identificate: ANAC le pubblica come dati d'impresa, la
  loro denominazione può contenere il nome del titolare e il progetto le tratta come persone giuridiche. Il
  README lo dichiara tra i limiti.
- I campi di testo libero non sono analizzati alla ricerca di nomi.
- Il numero di righe di persone fisiche compare nel report di qualità come controllo di tipo privacy.

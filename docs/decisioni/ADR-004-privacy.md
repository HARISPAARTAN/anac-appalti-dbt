# ADR-004: Privacy: nessuna persona fisica identificata nei file pubblicati

Stato: accettata (2026-10-25), aggiornata con la 0.1.1 (2026-10-25)

## Contesto

I file `aggiudicatari`, `partecipanti` e `subappalti` contengono anche persone fisiche (ditte individuali e
professionisti), con codice fiscale di 16 caratteri e nome completo: circa il 10 % delle righe in un campione dei
file reali. Anche l'anagrafe delle stazioni appaltanti (`stazioni-appaltanti`) e i lotti (`cig`) contengono
persone fisiche: ditte individuali, liberi professionisti e lavoratori autonomi che sono essi stessi stazioni
appaltanti. Il progetto è pubblico e non deve diffondere né ricostruire dati personali oltre ciò che serve alle
analisi aggregate. Nei pacchetti in ambito non esiste una colonna RUP o con nomi di responsabili.

La regola vale per ciò che il progetto **pubblica**: i mart nelle release, il repository, la documentazione e il sito.
Il warehouse e il landing sono locali e non vengono mai pubblicati; per questi la regola è più ampia dove è
possibile, ma ha limiti misurati e dichiarati qui sotto (punto 10).

La versione 0.1.0 aveva esteso la regola ai soli operatori (aggiudicatari, partecipanti, subappaltatori) e
aveva pubblicato, in `mart_stazioni_appaltanti`, nove stazioni che sono persone fisiche, sette con il nome
completo. La revisione finale lo ha trovato; l'asset è stato ritirato dalla release 0.1.0 e la 0.1.1 applica la
regola anche alle stazioni appaltanti (punto 9).

## Decisione

La privacy si ottiene non avendo mai l'identità a valle del download, non nascondendola dopo, dove la fonte lo
permette.

1. **Annullamento al landing per le colonne degli operatori.** La landing tiene solo le colonne del contratto
   marcate `tenere: true`. Prima di scrivere ogni Parquet di `aggiudicatari`, `partecipanti` e `subappalti`, le
   colonne `dato_personale: true` (`codice_fiscale`, `denominazione`, `cf_subappaltante`) passano dal
   classificatore dei codici fiscali: 11 cifre `persona_giuridica`, 16 caratteri secondo lo schema del codice
   personale `persona_fisica`, altro `non_verificabile`, vuoto `assente`. Codice e denominazione restano solo per
   `persona_giuridica`; negli altri casi diventano NULL. Quei tre Parquet non contengono codici fiscali né nomi di
   persone fisiche identificate da un codice personale (misurato: 0 codici personali nelle colonne
   `codice_fiscale`, `denominazione` e `cf_subappaltante`). Restano fuori da questa regola le ditte individuali
   con partita IVA (punto 10) e le colonne elencate nel perimetro (punto 11).
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
6. **Nel core, un unico operatore.** `dim_operatori` contiene gli operatori con codice di 11 cifre e due membri
   anonimi, `PERSONA_FISICA` e `NON_VERIFICABILE`. In `fct_partecipazioni` tutte le persone fisiche dello stesso
   lotto e ruolo confluiscono nella riga di `PERSONA_FISICA` (chiave CIG × operatore × ruolo) e il loro numero
   resta in `n_righe_partecipanti` e `n_righe_aggiudicatari`.
7. **Prove.** Test dbt verificano che nessun mart contenga codici fiscali personali
   (`assert_nessun_cf_personale_nei_mart`, anche sulle chiavi e sulle denominazioni delle stazioni), che nessuna
   chiave del mart delle stazioni corrisponda nell'anagrafe o nei lotti a una persona fisica
   (`assert_nessuna_stazione_personale_nei_mart`, per join sulla sorgente) e che nessuna colonna di staging,
   intermediate, core o radar si chiami come un dato personale (token `rup`, `nome`, `cognome`, `responsabile`:
   `assert_nessuna_colonna_personale`). Unit test dbt coprono la seconda linea di difesa di partecipanti e
   subappalti, le stazioni, le ditte individuali. Il classificatore Python e le macro SQL hanno gli stessi modelli e
   un test li confronta. Un test unitario cerca codici fiscali personali in tutti i documenti Markdown; la fixture
   è sintetica e non contiene persone fisiche.
8. **Scansione dei file rilasciati.** `appalti export` scansiona ogni colonna di testo dei nove Parquet: cerca il
   modello del codice fiscale personale e, per ogni codice fiscale personale dell'anagrafe delle stazioni
   appaltanti, il codice del cognome e quello del nome (le consonanti, come nel calcolo del codice fiscale) in
   parole di uno stesso testo di non più di sei parole e senza marcatori di ente. Se trova qualcosa cancella i file
   e fallisce; solo se la scansione è pulita scrive `ATTRIBUTION.md` e `SHA256SUMS`. Il controllo dei nomi è
   euristico (non trova una persona con una sola parola, né una il cui codice non è nell'anagrafe): le regole vere sono
   in staging e nella revisione manuale dei candidati (punto 9), la scansione è la prova a valle. Per questo l'affermazione
   è sempre "nessuna persona individuata dalle regole del codice, della forma giuridica e della revisione manuale", mai
   assoluta.
9. **Stazioni appaltanti che sono persone fisiche (0.1.1).** Una stazione è una persona fisica se il suo codice
   fiscale è di 16 caratteri oppure se la sua forma giuridica dice che è un individuo (ditta individuale, impresa
   individuale artigiana o commerciale, libero professionista, lavoratore autonomo; codici 56, 58, 59, 60, 61,
   A070). In staging (`stg_anac__stazioni_appaltanti`) codice fiscale, partita IVA, comune e denominazione
   diventano NULL o la dicitura anonima; la stessa regola vale sui lotti (`stg_anac__cig`: codice fiscale e
   denominazione dell'amministrazione appaltante) e per le amministrazioni assenti dall'anagrafe, il cui codice
   fiscale è personale nei lotti. Una terza regola, la revisione manuale, copre la classe che le due regole non vedono: nell'anagrafe
   ci sono stazioni con un codice segnaposto (`CFAVCP-…`, non di 11 cifre), forma giuridica "non classificato" e il
   nome e cognome di una persona. Il modello `int_stazioni_da_verificare` elenca ogni candidato (codice non di 11
   cifre, forma giuridica non classificata, non definita o assente, nome di 2-3 parole senza cifre e senza parole di
   ente) e il test `assert_candidati_stazioni_classificati` fallisce finché ogni candidato non è in uno di due seed
   di soli codici AUSA opachi, mai nomi: `ausa_persone_fisiche` (persona, trattata come ogni altra stazione che è
   una persona fisica) o `ausa_enti_verificati` (ente, con la data della revisione). Si legge il nome nella tabella
   di audit del test, solo in locale; nel dubbio è una persona. Procedura a ogni nuova esecuzione: se il test
   fallisce, classificare i nuovi candidati, aggiungere i codici al seed giusto e rieseguire. Origine dei casi nei
   seed: un primo caso è stato trovato dalla scansione dei file esportati, gli altri dalla revisione dei candidati
   (nell'esecuzione 20261025T160014-be23e3: 18 persone nel seed, 40 enti verificati; il primo caso è la scansione, i 17 successivi la revisione). Limite: i nomi di quattro parole o più e le voci con una forma giuridica
   nota o un codice di 11 cifre non entrano nella revisione.
   `int_stazioni` associa tutte queste stazioni a una sola chiave,
   `PERSONA_FISICA`, e quella chiave attraversa `dim_stazioni_appaltanti`, `fct_lotti`, `int_radar__lotti` e
   `mart_stazioni_appaltanti`: nei mart non c'è né il nome, né il codice AUSA, né il codice fiscale di una persona
   fisica. In questa esecuzione 401 (399 dell'anagrafe e 2 viste solo nei lotti) stazioni dell'anagrafe e dei lotti sono state anonimizzate.
10. **Ditte individuali con partita IVA (0.1.1, decisione del proprietario, reversibile).** Per il GDPR (art. 4,
    par. 1) un imprenditore individuale è una persona fisica: il suo nome commerciale e anche la sua partita IVA
    sono dati personali; la Corte di giustizia (cause C-92/09 e C-93/09) tutela le persone giuridiche solo quando
    il loro nome identifica persone fisiche, e il D.L. 201/2011 (art. 40) ha tolto la protezione alle persone
    giuridiche, non agli imprenditori individuali. ANAC le pubblica per obblighi di trasparenza (L. 190/2012
    art. 1 c. 32, D.Lgs. 33/2013 art. 37), ma quella base non autorizza il progetto a ripubblicarle. Quindi: gli
    operatori il cui `tipo_soggetto` è una forma giuridica individuale (`DITTA INDIVIDUALE`, `DITTE INDIVIDUALI`,
    `IMPRESE INDIVIDUALI ARTIGIANE`, `IMPRESE INDIVIDUALI COMMERCIALI`, `LAVORATORI AUTONOMI - PROFESSIONISTI`,
    `LIBERO PROFESSIONISTA`, `ALTRI LAVORATORI AUTONOMI`) perdono il nome in staging e in `dim_operatori`
    (dicitura anonima, `flag_ditta_individuale`), in una qualsiasi delle loro occorrenze. Il codice di 11 cifre
    resta come chiave locale, perché le aggregazioni contano operatori distinti, ma solo nel warehouse locale: nessun
    mart pubblicato porta nomi o codici di operatori (verificato: nessuno dei nove mart ha una colonna con nomi di
    operatori). In questa esecuzione 12.424 operatori sono ditte individuali con il nome annullato. La dicitura
    "IMPRESA SINGOLA (IMPRENDITORI INDIVIDUALI, ANCHE ARTIGIANI, SOCIETA' COMMERCIALI ...)" mescola persone e società
    e non si può separare con certezza: resta com'è e rientra nei limiti. La scelta è la più protettiva tra quelle
    ragionevoli e si può invertire (basta togliere la condizione dal modello `stg_anac__*` e da `int_operatori`).
11. **Testo libero (0.1.1).** Nelle colonne di testo libero dei contratti (`testo_libero: true`: `oggetto_gara`,
    `oggetto_lotto`, `motivo_cancellazione` del CIG, `oggetto` dei subappalti, `motivo_variante`) ogni codice
    fiscale personale di 16 caratteri viene sostituito dal token `[CF]` al landing; il numero di sostituzioni è
    contato nel registro, nel log di atterraggio e nel report di qualità (in questa esecuzione 794
    sostituzioni). I **nomi** nel testo libero non sono riconosciuti: non si possono misurare e ce ne sono di
    sicuro più dei codici. Il testo libero non entra in nessun mart.
12. **Perimetro e limiti misurati.** Il progetto non pubblica il landing, il warehouse né l'archivio raw. In
    locale restano questi casi, misurati nell'esecuzione 20261025T160014-be23e3: (a) l'archivio raw (`data/raw/`) conserva i file
    ANAC originali, compresi i dati personali, perché è l'unica copia storica dei delta superati (vedi ADR-003);
    (b) il landing dell'anagrafe `stazioni_appaltanti` conserva i 361 codici fiscali personali con i
    nomi come ANAC li pubblica (l'annullamento avviene in staging); (c) il landing dei lotti conserva
    91 righe (11 codici) in cui `cf_amministrazione_appaltante` è un codice
    personale; (d) il landing di operatori conserva il nome delle ditte individuali con partita IVA (annullato in
    staging, vedi punto 10); (e) i nomi nel testo libero. Nessuno di questi è un file del repository o del sito, e il
    sito di documentazione è generato sulla fixture sintetica.

## Alternative scartate

- Pseudonimo HMAC del codice fiscale: resta un dato personale, richiede un segreto e aggiunge poco a mart
  aggregati.
- Annullare le identità solo in staging: il Parquet di landing conterrebbe dati personali in chiaro, con una
  superficie di esposizione molto più ampia. Per gli operatori si annulla al landing; per l'anagrafe delle
  stazioni e i nomi delle ditte individuali l'annullamento è in staging (limiti 12 b-d).
- Escludere del tutto le righe delle persone fisiche: falserebbe i conteggi di partecipanti e aggiudicatari.
- Collassare le persone fisiche in una sola riga già al landing: l'impronta di riga non distinguerebbe più i
  partecipanti e il conteggio andrebbe perso.
- Togliere `denominazione` da `dim_operatori` per tutti: nessun mart la usa, ma serve a leggere i dati in locale;
  si annulla solo dove è un dato personale.

## Conseguenze

- Le analisi per operatore non distinguono tra persone fisiche diverse e non seguono una persona nel tempo. Le
  ditte individuali si contano come operatori distinti per codice, ma non hanno un nome nel warehouse.
- Il nome e la partita IVA di un imprenditore individuale sono dati personali ai sensi del GDPR. Il progetto
  non li pubblica; ne conserva il solo codice, in locale, come chiave tecnica (interesse legittimo all'analisi di
  dati aperti sugli appalti, fonte pubblica; l'informativa individuale richiederebbe uno sforzo sproporzionato,
  art. 14, par. 5, lett. b).
- Il mart delle stazioni appaltanti ha un solo membro `PERSONA_FISICA` per le stazioni che sono persone fisiche: la
  riga mostra solo conteggi e importi aggregati.
- Il numero di righe di persone fisiche, di stazioni e operatori anonimizzati e di codici mascherati nel testo
  compare nel report di qualità come controllo di tipo privacy.
- I limiti del punto 12 sono dichiarati nel README (Limiti) e in `data/LICENSE-DATA.md`.

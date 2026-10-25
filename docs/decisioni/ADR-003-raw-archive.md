# ADR-003: Estrazione incrementale e archivio raw append-only con manifest SHA-256

Stato: accettata (2026-10-25)

## Contesto

ANAC pubblica file annuali e delta mensili e a volte ripubblica un file con lo stesso nome. I delta superati
spariscono dal portale. Senza una copia locale degli originali una ricostruzione storica non è più possibile, e
un'esecuzione ripetuta non deve scaricare di nuovo ciò che è già presente.

Tre fatti verificati sul portale il 2026-10-25 condizionano la decisione:

- La dimensione che CKAN dichiara per una risorsa è quella del CSV non compresso, non dello zip (per esempio
  `cig_csv_2024_01`: 30.163.236 byte dichiarati, 6.461.968 byte di zip). I file in ambito sommano circa 9 GB
  dichiarati e circa 2 GB di zip reali.
- Il WAF del portale risponde HTTP 200 con una pagina HTML "Request Rejected … Your support ID is …". Lo stato
  HTTP non basta per riconoscere un rifiuto. Lo User-Agent del progetto
  (`anac-appalti-dbt/0.1 (+https://github.com/HARISPAARTAN/anac-appalti-dbt)`) è passato sui download e su
  `package_show` del vocabolario, ma è stato rifiutato su `package_show?id=cig-2025`; uno User-Agent da browser
  è passato ovunque.
- Le intestazioni reali dei CSV non coincidono del tutto con quelle attese dalla specifica (per esempio il file
  CIG ha 61 colonne e le ultime sono scritte in maiuscolo, come `COD_ESITO` e `FLAG_PNRR_PNC`). Separatore `;`, valori non vuoti tra virgolette,
  UTF-8 senza BOM, date ISO, punto decimale.

## Decisione

Ogni zip scaricato viene conservato intatto in `data/raw/anac/{pacchetto}/` con nome
`{radice}__{last_modified}__{sha8}.zip`. Il manifest `data/raw/_manifest.csv` è append-only e registra URL,
dimensione, `last_modified`, SHA-256 e righe attese dal logCsv. Un file si scarica solo se è nuovo o se cambia
`last_modified` o la dimensione; uno zip con SHA-256 già noto non viene duplicato. Lo SHA-256 viene riverificato a
ogni lettura. La landing legge solo dall'archivio, quindi `appalti run --da-archivio` ricostruisce tutto senza
rete e registra anche gli zip scaricati a mano dal browser.

Il client CKAN riconosce il WAF dal corpo della risposta (titolo "Request Rejected" e support ID), non dallo
stato. Al primo rifiuto passa una volta sola allo User-Agent da browser
(`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36`)
e registra nel riepilogo di estrazione (e quindi nel log di esecuzione) quale dei due ha funzionato. Se anche il
secondo viene rifiutato, l'estrazione fallisce con `WafRifiuto` e un messaggio con il support ID; non c'è
nessun altro tentativo di aggirare il WAF. `APPALTI_USER_AGENT` sostituisce lo User-Agent iniziale.

Le intestazioni reali sono lette con `appalti intestazioni` (richiesta HTTP Range sui primi 128 KB di uno zip per
pacchetto) e salvate in `contratti/anac/_intestazioni_reali.json`. I contratti di sorgente
(`contratti/anac/*.yml`) sono scritti su quelle intestazioni e la landing tiene solo le colonne `tenere: true`.

## Alternative scartate

- Atterrare direttamente in Parquet e cancellare gli zip: perde i delta superati e la prova dell'origine.
- Snapshot dbt (SCD2) su milioni di righe: costosi, e l'archivio raw conserva già la storia.
- Usare sempre lo User-Agent da browser: funziona, ma nasconde il client reale; si preferisce identificarsi e
  ripiegare solo se il WAF rifiuta.
- Fidarsi dello stato HTTP: il WAF risponde 200 al rifiuto.
- Scaricare i file completi per leggere le intestazioni: la richiesta Range basta e risparmia gigabyte.

## Conseguenze

- Le esecuzioni sono idempotenti: una seconda esecuzione identica non scarica e non atterra nulla e produce le
  stesse impronte per modello (test di integrazione).
- L'archivio occupa circa 2 GB per 2024–2026 (stima dalle dimensioni dichiarate, da misurare alla prima
  esecuzione completa) e resta locale e fuori da git. Conserva i file ANAC originali, quindi anche i dati delle
  persone fisiche: vedi ADR-004.
- `int_cig__versioni` conserva una versione per file; `int_cig__corrente` sceglie la più recente per data di
  snapshot.
- Con il portale bloccato per entrambi gli User-Agent la via d'uscita è il download dal browser e
  `appalti run --da-archivio`.

# ADR-002: Dagster come orchestratore

Stato: accettata (2026-10-25)

## Contesto

Serve un orchestratore che mostri dipendenze, ripartenze e pianificazione, senza servizi da amministrare su una
macchina singola e con un collegamento naturale ai modelli dbt. Una pipeline pianificata non deve mai risultare
verde quando fallisce.

## Decisione

Dagster con `dagster-dbt`. Ogni pacchetto ANAC ha un asset raw (con tre ripetizioni a 60 secondi) e un asset di
landing; ogni modello dbt è un asset; l'asset `riepilogo_qualita` dipende da tutti i modelli e porta il
controllo `qualita_dati`. Il job `pipeline_completo` materializza tutto con l'esecutore in processo; il sensor
`ckan_aggiornato` interroga `package_search` una volta al giorno e avvia il job solo se un pacchetto in ambito è
cambiato; la schedule `mensile_25` (06:00, Europe/Rome) è la riserva. Sensor e schedule partono spenti: contattano
il portale e si accendono a mano nel daemon, mai in CI. `appalti run` esegue gli stessi asset in processo con
`materialize`, quindi CLI e interfaccia usano lo stesso codice.

Gli errori fanno fallire gli asset, non solo il comando: un file non atterrato (`landing_*`) o un `dbt build` che
termina con errori (`modelli_dbt`) sollevano un'eccezione, così lo stato dell'esecuzione Dagster è FAILURE
anche per le esecuzioni lanciate da schedule, sensor o interfaccia, e `riepilogo_qualita` non parte su dati
incompleti. `appalti run` ricava gli stessi errori, scrive `esito: errore` nel log di esecuzione ed esce con
codice 1.

## Alternative scartate

- Airflow: richiede container, scheduler e database di metadati, sproporzionati per un progetto su una macchina.
- Solo CLI Python senza orchestratore: lascia scoperta proprio la competenza di orchestrazione.
- Prefect: valido, ma il grafo di asset di Dagster corrisponde uno a uno ai modelli dbt.
- Esecutore multiprocesso (predefinito di Dagster) per il job: gli otto asset raw colpirebbero il portale in
  parallelo e gli asset di landing riscrivono per intero il registro `_registro.csv`, quindi due landing
  concorrenti possono perdersi righe a vicenda. Il job usa l'esecutore in processo, come `appalti run`.

## Conseguenze

- `uv run dagster dev -m anac_appalti.definitions` mostra il grafo completo senza configurazione aggiuntiva.
- Il manifest dbt deve esistere quando Dagster carica le definizioni: `garantisci_manifest` esegue `dbt parse`
  se manca o è più vecchio dei sorgenti dbt.
- La CI valida le definizioni con `dagster definitions validate`; i test verificano che schedule e sensor siano
  spenti, che `riepilogo_qualita` dipenda dai modelli dbt e che un errore di landing o di dbt faccia fallire
  l'esecuzione.
- I tentativi automatici degli asset raw valgono anche per errori deterministici (per esempio un rifiuto del
  WAF): con il portale bloccato passano alcuni minuti prima del messaggio di errore.
- Gli asset dbt vengono eseguiti come un solo `dbt build`: se un test di gravità errore fallisce, i modelli già
  costruiti restano nel warehouse, ma l'esecuzione risulta fallita.

# Licenza dei dati

Il codice di questo repository è rilasciato con licenza MIT (vedi `LICENSE`).

I dati derivati pubblicati dal repository (i mart aggregati in `data/export/` e negli asset delle release)
sono elaborazioni dei dati aperti ANAC e sono rilasciati con la stessa licenza della fonte,
Creative Commons Attribuzione – Condividi allo stesso modo 4.0 Internazionale (CC BY-SA 4.0,
https://creativecommons.org/licenses/by-sa/4.0/deed.it).

Attribuzione richiesta:

Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati

La fixture in `data/fixtures/` è sintetica: è generata da `appalti fixture genera`, non contiene dati ANAC
reali né dati di persone fisiche.

## English

Code is MIT. Derived data (aggregate marts in `data/export/` and in release assets) is processed ANAC open
data and is released under CC BY-SA 4.0 with the attribution above. The fixture in `data/fixtures/` is
synthetic and contains no real ANAC records and no personal data.

## Dati personali nel landing / Personal data in the landing zone

L'archivio raw (`data/raw/`, non versionato) conserva i file ANAC scaricati così come sono: è la copia storica,
perché ANAC rimuove i delta superati. Il landing in Parquet (`data/landing/`) non contiene invece identificativi
di persone fisiche: prima di scrivere ogni Parquet, `appalti` passa le colonne `dato_personale` dei contratti
(`codice_fiscale`, `denominazione`, `cf_subappaltante`) dal classificatore dei codici fiscali. Il codice fiscale
resta solo se è una partita IVA di 11 cifre; la denominazione solo se il codice fiscale della stessa riga lo è;
negli altri casi (16 caratteri di persona fisica, valori non verificabili, assenti) il valore è NULL. Anche
l'impronta di riga `_hash_riga` è calcolata sui valori già ripuliti, quindi due righe che differiscono solo per
l'identità di una persona fisica hanno la stessa impronta. Lo staging dbt annulla gli stessi valori una seconda
volta. I campi di testo libero non sono analizzati; nei pacchetti in ambito non esiste una colonna RUP.

The raw archive (`data/raw/`, git-ignored) keeps the downloaded ANAC files untouched, as the only historical copy.
The Parquet landing zone (`data/landing/`) holds no natural-person identifiers: before each Parquet is written,
the contract columns flagged `dato_personale` go through the tax-code classifier. A tax code is kept only if it is
an 11-digit VAT number; the name is kept only if the same row's tax code is; otherwise the value is NULL. The row
hash `_hash_riga` is computed on the already cleaned values. dbt staging blanks the same values a second time.
Free-text fields are not scanned; no in-scope package has a RUP column.

# ADR-005: Licenza CC BY-SA 4.0 per i dati derivati

Stato: accettata (2026-10-25)

## Contesto

Tutti i pacchetti CSV usati sono pubblicati da ANAC con licenza CC BY-SA 4.0 (`license_id` `CC-BY-SA-4.0`,
verificato il 2026-10-25). La clausola "condividi allo stesso modo" si applica a ogni dato derivato che il
progetto pubblica.

## Decisione

- Il codice resta MIT.
- I dati derivati pubblicati (i nove mart aggregati, negli asset delle release) sono CC BY-SA 4.0, con
  l'attribuzione testuale
  "Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati"
  nel README, in `data/LICENSE-DATA.md` e nei metadati di ogni file Parquet esportato (`appalti export`).
- Si pubblicano solo aggregati: nessun fatto a livello di lotto o di operatore lascia la macchina.
- Il sito della documentazione dbt è generato sulla fixture sintetica e non contiene righe di dati reali.

## Alternative scartate

- Pubblicare anche i fatti di dettaglio: più utile per terzi, ma più dati da tutelare e nessun vantaggio per il
  report Appalti Radar.
- Licenziare i dati derivati come MIT insieme al codice: non compatibile con la licenza della fonte.

## Conseguenze

- Chi riusa i mart deve mantenere attribuzione e licenza.
- Il feed OCDS (CC BY 4.0), se aggiunto, avrà un'attribuzione propria.
- La licenza dei dati non cambia il fatto che i dati personali non sono mai pubblicati (ADR-004).

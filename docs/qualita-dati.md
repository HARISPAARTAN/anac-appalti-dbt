# Qualità dei dati (report sulla fixture sintetica)

**Questo è il report della fixture sintetica, non dei dati ANAC reali.** Ogni numero qui sotto viene da dati generati dal progetto per test e CI. Dopo l'esecuzione completa su dati reali (`uv run appalti run`, poi `uv run appalti report`) questo file viene sostituito dal report reale.

Generato da `appalti report --fixtures` sulla fixture sintetica (mese 2), data di riferimento 2026-10-25.

Politica: si segnala, non si cancella. Ogni controllo è un test dbt (avviso o errore) e un flag in `int_lotti__qualita`.

## Volumi

| Misura | Valore |
|---|---:|
| Righe CIG atterrate | 1.704 |
| Versioni di lotto (CIG × file) | 1.551 |
| Lotti correnti (un CIG per riga) | 1.500 |
| Lotti nei mart Radar | 1.499 |
| Lotti derivati da accordo quadro (esclusi dalle somme) | 60 |
| Lotti cancellati (esclusi dal Radar) | 1 |
| File atterrati / riconciliati / non verificabili | 11 / 9 / 2 |

## Controlli

| Controllo | Regola | Gravità | Valore | Quota |
|---|---|---|---:|---:|
| Riconciliazione | Righe atterrate per file = numero_righe del logCsv ANAC | errore | 0 | 0,00 % |
| Duplicati esatti | Righe identiche nello stesso file (contate, una versione tenuta) | avviso | 3 | 0,18 % |
| Duplicati in conflitto | Stesso CIG, righe prevalenti diverse nello stesso file | avviso | 0 | 0,00 % |
| Date impossibili | Scadenza o aggiudicazione prima della pubblicazione; date prima del 2007 o oltre due anni | avviso | 3 | 0,20 % |
| Importi anomali | ≤ 0, oltre il totale di gara, oltre 5 miliardi, non leggibili o oltre 3 MAD (log10) nel gruppo CPV × oggetto; esclusi dalle somme | avviso | 3 | 0,20 % |
| Importo non leggibile | Testo dell'importo che non si legge (formato sconosciuto, oltre decimal(18,2)): resta in *_raw, il lotto è escluso dalle somme | avviso | 0 | 0,00 % |
| Aggiudicazione non leggibile | Importo o ribasso di aggiudicazione che non si legge (testo originale in *_raw) | avviso | 0 | 0,00 % |
| Date non leggibili | Data di pubblicazione, scadenza, aggiudicazione, variante o subappalto con testo non vuoto e valore NULL: il lotto manca dai mart a base temporale | avviso | 0 | 0,00 % |
| Conteggi di offerte non leggibili | Offerte ammesse o imprese offerenti con testo non vuoto e valore NULL: il lotto esce dalla logica dell'offerta unica | avviso | 0 | 0,00 % |
| Aggiudicatario mancante | Lotto aggiudicato senza righe in aggiudicatari | avviso | 2 | 0,13 % |
| Stazione orfana | codice_ausa assente dall'anagrafe | avviso | 0 | 0,00 % |
| Aggiudicazione orfana | CIG dell'aggiudicazione assente dai dati CIG in ambito (atteso per lotti pubblicati prima dell'anno minimo) | avviso | 0 | – |
| Ribasso fuori intervallo | Ribasso fuori da 0–100 % | avviso | 1 | – |
| Persone fisiche | Codice fiscale di 16 caratteri: identità annullata al landing (e di nuovo in staging), conteggio conservato | privacy | 0 | 0,00 % |

Dettaglio importi anomali: non positivi 1, oltre il totale di gara 1, oltre 5 miliardi 1, anomali per MAD 1, non leggibili 0 (un lotto può avere più flag).

Regole sulle somme: gli importi si sommano solo sui lotti non derivati da accordo quadro, non anomali e non cancellati, così un accordo quadro e i suoi contratti attuativi non sono contati due volte. I lotti esclusi restano nei conteggi.

Le perdite di lettura (date e conteggi) sono contate su tutte le righe atterrate, anche sulle versioni superate; il dettaglio per colonna è in `intermediate.int_perdite_parsing` e ogni colonna ha un test dbt `perdita_parsing` di livello avviso sulla source.

I file annuali `cig-AAAA` non hanno un conteggio CSV nel logCsv ANAC (solo TTL): la loro riconciliazione è `non_disponibile`.

Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati

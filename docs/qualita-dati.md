# Qualità dei dati

Generato da `appalti report` sui dati reali ANAC con data di riferimento 2026-10-25.

Politica: si segnala, non si cancella. Ogni controllo è un test dbt (avviso o errore) e un flag in `int_lotti__qualita`.

## Volumi

| Misura | Valore |
|---|---:|
| Righe CIG atterrate | 6.334.426 |
| Versioni di lotto (CIG × file) | 6.174.107 |
| Lotti correnti (un CIG per riga) | 3.734.851 |
| Lotti nei mart Radar | 3.734.842 |
| Lotti derivati da accordo quadro (esclusi dalle somme) | 907.159 |
| Lotti cancellati (esclusi dal Radar) | 9 |
| File atterrati / riconciliati con il logCsv / riconciliati con i record contati / non verificabili | 73 / 49 / 24 / 0 |

## Controlli

| Controllo | Regola | Gravità | Valore | Quota |
|---|---|---|---:|---:|
| Riconciliazione | Righe atterrate per file = numero_righe del logCsv ANAC (o record contati nel CSV) | errore | 0 | 0,00 % |
| Duplicati esatti | Righe identiche nello stesso file (contate, una versione tenuta) | avviso | 1.663 | 0,03 % |
| Duplicati in conflitto | Stesso CIG, righe prevalenti diverse nello stesso file | avviso | 0 | 0,00 % |
| Date impossibili | Scadenza o aggiudicazione prima della pubblicazione; date prima del 2007 o oltre due anni | avviso | 2.520.462 | 67,48 % |
| Importi anomali | ≤ 0, oltre il totale di gara, oltre 5 miliardi, non leggibili o oltre 3 MAD (log10) nel gruppo CPV × oggetto; esclusi dalle somme | avviso | 150.243 | 4,02 % |
| Importo non leggibile | Testo dell'importo che non si legge (formato sconosciuto, oltre decimal(18,2)): resta in *_raw, il lotto è escluso dalle somme | avviso | 1 | 0,00 % |
| Aggiudicazione non leggibile | Importo o ribasso di aggiudicazione che non si legge (testo originale in *_raw) | avviso | 53 | 0,00 % |
| Date non leggibili | Data di pubblicazione, scadenza, aggiudicazione, variante o subappalto con testo non vuoto e valore NULL: il lotto manca dai mart a base temporale | avviso | 0 | 0,00 % |
| Conteggi di offerte non leggibili | Offerte ammesse o imprese offerenti con testo non vuoto e valore NULL: il lotto esce dalla logica dell'offerta unica | avviso | 0 | 0,00 % |
| Aggiudicatario mancante | Lotto aggiudicato senza righe in aggiudicatari | avviso | 58.961 | 1,58 % |
| Stazione orfana | codice_ausa assente dall'anagrafe | avviso | 368 | 0,01 % |
| Aggiudicazione orfana | CIG dell'aggiudicazione assente dai dati CIG in ambito (atteso per lotti pubblicati prima dell'anno minimo) | avviso | 2.413.720 | – |
| Subappalti collassati | Righe diverse con lo stesso id_subappalto nello stesso file: ne resta una in fct_subappalti | avviso | 13.826 | – |
| Varianti collassate | Righe diverse con lo stesso id_variante nello stesso file: ne resta una in fct_varianti | avviso | 18.378 | – |
| Ribasso fuori intervallo | Ribasso fuori da 0–100 % | avviso | 19.654 | – |
| Persone fisiche | Codice fiscale di 16 caratteri: identità annullata al landing (e di nuovo in staging), conteggio conservato | privacy | 1.631.723 | 7,65 % |
| Stazioni appaltanti persone fisiche | Codice fiscale di 16 caratteri o forma giuridica individuale: nome e codici annullati in staging, chiave unica PERSONA_FISICA nei mart | privacy | 401 | – |
| Operatori ditte individuali | tipo_soggetto individuale: nome annullato in staging, codice di 11 cifre tenuto come chiave locale (mai pubblicato) | privacy | 12.424 | – |
| Codici nel testo libero | Codice fiscale di 16 caratteri trovato nel testo libero (oggetto di gara, lotto, subappalto, motivi): sostituito da [CF] al landing; i nomi di persona nel testo non sono riconosciuti | privacy | 794 | – |

Dettaglio importi anomali: non positivi 15.426, oltre il totale di gara 3.841, oltre 5 miliardi 37, anomali per MAD 131.173, non leggibili 1 (un lotto può avere più flag).

Date impossibili sui dati reali: la regola "scadenza prima della pubblicazione" scatta soprattutto sugli affidamenti diretti, dove la data di scadenza dell'offerta può precedere la pubblicazione senza che ci sia un errore. Misura: 97,68 % dei lotti segnalati sono affidamenti diretti, e la scadenza prima della pubblicazione spiega 85,56 % delle segnalazioni (negli affidamenti diretti di questo tipo la scadenza precede la pubblicazione in media di 11 giorni); il resto sono aggiudicazioni anteriori alla pubblicazione o date fuori dall'intervallo plausibile. Il controllo è informativo e non esclude lotti dai mart.

Subappalti e varianti collassati: `int_subappalti__corrente` e `int_varianti__corrente` tengono una riga per id, quindi le altre righe diverse con lo stesso id nello stesso file non arrivano ai fatti. In questa esecuzione: 13.826 righe di subappalto scartate (10.592 id, di cui 4.702 con più subappaltatori identificabili) e 18.378 righe di variante (14.749 id). I test dbt `dq_subappalti_collassati` e `dq_varianti_collassate` (avviso) le contano a ogni esecuzione; la correzione (grana id più ordinale) è in roadmap per la 0.2.0.

Revisione manuale delle stazioni appaltanti: nell'anagrafe ci sono stazioni con un codice segnaposto, forma giuridica non classificata e il nome di una persona, che le regole del codice fiscale e della forma giuridica non vedono. `int_stazioni_da_verificare` elenca i candidati (codice non di 11 cifre, forma giuridica non classificata, non definita o assente, nome di 2-3 parole senza cifre e senza parole di ente) e il test `assert_candidati_stazioni_classificati` fallisce finché ciascuno non è nel seed delle persone o in quello degli enti verificati. In questa esecuzione: 40 candidati rimasti in elenco (enti già verificati: se il test passa non ne manca nessuno), 18 codici nel seed delle persone, 40 nel seed degli enti verificati.

Regole sulle somme: gli importi si sommano solo sui lotti non derivati da accordo quadro, non anomali e non cancellati, così un accordo quadro e i suoi contratti attuativi non sono contati due volte. I lotti esclusi restano nei conteggi.

Le perdite di lettura (date e conteggi) sono contate su tutte le righe atterrate, anche sulle versioni superate; il dettaglio per colonna è in `intermediate.int_perdite_parsing` e ogni colonna ha un test dbt `perdita_parsing` di livello avviso sulla source.

I file annuali `cig-AAAA` non hanno un conteggio CSV nel logCsv ANAC (solo TTL). Dalla 0.1.1 il landing li riconcilia con i record contati nel CSV (stati `ok_fisico` e `differenza_fisica`, distinti da `ok` e `differenza` del logCsv). In questa esecuzione: 49 file `ok`, 24 `ok_fisico`, 0 con differenza, 0 `non_disponibile`.

Misura del 25 ottobre 2026 sull'archivio raw (73 file, script esterno al lettore): i record fuori dalle virgolette coincidono con le righe atterrate in tutti i 49 file con conteggio nel logCsv e nei 24 file annuali `cig-2024` e `cig-2025` (2.704.490 righe), quindi nessuna riga è andata persa; il semplice conteggio degli a capo sbaglia in 7 file dei delta CIG, che hanno a capo dentro i campi. Il conteggio condivide con il lettore la regola del backslash e non garantisce di rilevare un backslash isolato (nei 73 file ce ne sono 0; ANAC raddoppia i backslash letterali, 863 coppie `\\`).

Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati

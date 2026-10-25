# Glossario

Termini del dominio e del progetto in italiano, inglese e tedesco. I nomi di tabelle e colonne del progetto
usano i termini italiani della prima colonna. Torna al [README](../README.md).

| Italiano | English | Deutsch | Nota |
|---|---|---|---|
| appalto pubblico | public procurement contract | öffentlicher Auftrag | |
| stazione appaltante | contracting authority | öffentlicher Auftraggeber | `dim_stazioni_appaltanti` |
| codice AUSA | AUSA code (contracting-authority register code) | AUSA-Code (Register der Auftraggeber) | chiave dell'anagrafe |
| CIG (codice identificativo gara) | tender identification code | Vergabekennnummer (CIG) | un CIG per lotto |
| gara | tender | Ausschreibung | |
| lotto | lot | Los | `fct_lotti` |
| importo del lotto | lot value | Auftragswert des Loses | |
| oggetto principale del contratto | main contract type (works, services, supplies) | Hauptgegenstand (Bau, Dienstleistung, Lieferung) | |
| procedura di scelta del contraente | award procedure | Vergabeverfahren | `dim_procedure` |
| procedura aperta | open procedure | offenes Verfahren | |
| procedura ristretta | restricted procedure | nicht offenes Verfahren | |
| procedura negoziata | negotiated procedure | Verhandlungsverfahren | |
| affidamento diretto | direct award | Direktvergabe | |
| accordo quadro | framework agreement | Rahmenvereinbarung | |
| scadenza delle offerte | bid deadline | Angebotsfrist | |
| offerta | bid | Angebot | |
| offerta unica | single bid | Einzelangebot | indicatore di concorrenza |
| aggiudicazione | award | Zuschlag | `fct_aggiudicazioni` |
| aggiudicatario | winning bidder | Zuschlagsempfänger | |
| partecipante | bidder | Bieter | `fct_partecipazioni` |
| ribasso | discount on the base price | Preisnachlass | percentuale |
| variante | contract modification | Vertragsänderung | `fct_varianti` |
| subappalto | subcontracting | Unterauftragsvergabe | `fct_subappalti` |
| CPV | Common Procurement Vocabulary | Gemeinsames Vokabular für öffentliche Aufträge (CPV) | `dim_cpv` |
| PNRR | National Recovery and Resilience Plan | Nationaler Aufbau- und Resilienzplan | |
| codice fiscale | tax code | Steuernummer (Codice fiscale) | |
| partita IVA | VAT number | Umsatzsteuer-Identifikationsnummer | 11 cifre |
| persona fisica | natural person | natürliche Person | identità annullata |
| persona giuridica | legal entity | juristische Person | |
| ditta individuale | sole trader | Einzelunternehmen | |
| annullamento dell'identità | blanking of the identity | Unkenntlichmachung der Identität | al landing, ripetuto in staging |
| regione (NUTS 2) | region (NUTS 2) | Region (NUTS 2) | `dim_territorio` |
| ANAC | National Anti-Corruption Authority | Nationale Antikorruptionsbehörde | editore dei dati |
| dati aperti | open data | offene Daten | |
| archivio raw | raw archive | Rohdatenarchiv | zip originali |
| manifest | manifest | Manifest | `data/raw/_manifest.csv` |
| landing | landing zone | Landing-Zone | Parquet |
| contratto di sorgente | source contract | Datenvertrag | `contratti/anac/*.yml` |
| contratto del modello | model contract | Modellvertrag | applicato ai mart Radar |
| schema a stella | star schema | Sternschema | |
| mart | data mart | Data Mart | `marts/radar` |
| asset | asset | Asset | unità del grafo Dagster |
| orchestratore | orchestrator | Orchestrator | Dagster |
| freschezza | freshness | Aktualität | `dbt source freshness` |
| idempotenza | idempotency | Idempotenz | stesse impronte a ogni esecuzione |
| riconciliazione | reconciliation | Abgleich | righe contro logCsv |
| fixture sintetica | synthetic fixture | synthetische Testdaten | non contiene dati ANAC reali |
| esecuzione completa | full run | vollständiger Lauf | su dati reali 2024–2026 |
| data di riferimento | reference date | Stichtag | |

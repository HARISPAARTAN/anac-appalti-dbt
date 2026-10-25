{% docs __overview__ %}

# anac-appalti-dbt

Pipeline di analytics engineering sui dati aperti ANAC degli appalti pubblici: landing in Parquet,
dbt-core su DuckDB (staging, livello intermedio versionato, schema a stella `core`, nove mart Radar).
I nomi di modelli e colonne sono in italiano; i prefissi dbt (`stg_`, `int_`, `dim_`, `fct_`, `mart_`) in inglese.

Fonte: ANAC – Autorità Nazionale Anticorruzione, dati.anticorruzione.it, licenza CC BY-SA 4.0; dati elaborati.

Questa documentazione è generata dalla CI su una fixture sintetica: non contiene dati reali né dati personali.

English: dbt documentation of an Italian public-procurement pipeline (ANAC open data), generated from a
synthetic fixture. Derived data is licensed CC BY-SA 4.0.

{% enddocs %}

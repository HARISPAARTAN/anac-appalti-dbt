-- Una riga per CIG: la versione più recente per _data_snapshot e poi per _risorsa.
-- Incrementale: ricalcola solo i CIG con versioni atterrate dopo l'ultimo caricamento.
-- Se cambia anno_minimo serve `dbt build --full-refresh`.
{{
    config(
        materialized='incremental',
        unique_key='cig',
        incremental_strategy='delete+insert'
    )
}}

with versioni as (
    select * from {{ ref('int_cig__versioni') }}
    where coalesce(year(data_pubblicazione), {{ var('anno_minimo') }}) >= {{ var('anno_minimo') }}
)

select * exclude (ordine_versione)
from versioni
where ordine_versione = 1
{% if is_incremental() %}
    and cig in (
        select cig from versioni
        where _caricato_il > (select coalesce(max(_caricato_il), timestamp '1900-01-01') from {{ this }})
    )
{% endif %}

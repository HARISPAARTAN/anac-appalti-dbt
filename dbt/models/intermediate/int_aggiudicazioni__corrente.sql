-- Una riga per id_aggiudicazione: la versione più recente (stessa regola di int_cig__corrente).
{{
    config(
        materialized='incremental',
        unique_key='id_aggiudicazione',
        incremental_strategy='delete+insert'
    )
}}

with ordinate as (
    select
        *,
        count(*) over (partition by id_aggiudicazione) as n_versioni,
        row_number() over (
            partition by id_aggiudicazione
            order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as ordine_versione
    from {{ ref('stg_anac__aggiudicazioni') }}
    where id_aggiudicazione is not null and cig is not null
)

select * exclude (ordine_versione)
from ordinate
where ordine_versione = 1
{% if is_incremental() %}
    and id_aggiudicazione in (
        select id_aggiudicazione from ordinate
        where _caricato_il > (select coalesce(max(_caricato_il), timestamp '1900-01-01') from {{ this }})
    )
{% endif %}

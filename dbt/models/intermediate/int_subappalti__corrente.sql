-- Una riga per subappalto: la versione più recente.
with ordinate as (
    select
        *,
        row_number() over (
            partition by id_subappalto
            order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as ordine_versione
    from {{ ref('stg_anac__subappalti') }}
    where id_subappalto is not null and cig is not null
)

select * exclude (ordine_versione)
from ordinate
where ordine_versione = 1

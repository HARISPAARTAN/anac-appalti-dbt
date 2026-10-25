{{ config(severity='warn') }}
-- Avviso: righe di subappalto scartate da int_subappalti__corrente. Il modello tiene una riga per id_subappalto, ma
-- nello stesso file lo stesso id può avere più righe diverse (più subappaltatori di un raggruppamento temporaneo):
-- tutte tranne una spariscono da fct_subappalti. Una riga per riga scartata (stesso file della riga tenuta,
-- contenuto diverso); i duplicati esatti non contano. La correzione strutturale (grana id, ordinale) è in roadmap.
with righe as (
    select distinct id_subappalto, _data_snapshot, _risorsa, _hash_riga
    from {{ ref('stg_anac__subappalti') }}
    where id_subappalto is not null and cig is not null
),

ordinate as (
    select
        *,
        row_number() over (
            partition by id_subappalto order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as ordine,
        first_value(_risorsa) over (
            partition by id_subappalto order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as risorsa_tenuta
    from righe
)

select id_subappalto, _risorsa, _hash_riga
from ordinate
where ordine > 1 and _risorsa = risorsa_tenuta

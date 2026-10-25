{{ config(severity='warn') }}
-- Avviso: righe di variante scartate da int_varianti__corrente. Il modello tiene una riga per id_variante, ma nello
-- stesso file lo stesso id può avere più righe diverse (anche su CIG diversi): tutte tranne una spariscono da
-- fct_varianti. Una riga per riga scartata (stesso file della riga tenuta, contenuto diverso); i duplicati esatti
-- non contano. La correzione strutturale (grana id, ordinale) è in roadmap.
with righe as (
    select distinct id_variante, _data_snapshot, _risorsa, _hash_riga
    from {{ ref('stg_anac__varianti') }}
    where id_variante is not null and cig is not null
),

ordinate as (
    select
        *,
        row_number() over (
            partition by id_variante order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as ordine,
        first_value(_risorsa) over (
            partition by id_variante order by _data_snapshot desc, _risorsa desc, _hash_riga desc
        ) as risorsa_tenuta
    from righe
)

select id_variante, _risorsa, _hash_riga
from ordinate
where ordine > 1 and _risorsa = risorsa_tenuta

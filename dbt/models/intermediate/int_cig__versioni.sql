-- Una riga per CIG e file: la versione del lotto è la riga del CPV prevalente.
-- Duplicati esatti (stesso _hash_riga nello stesso file) contati, non persi.
with righe as (
    select * from {{ ref('stg_anac__cig') }}
    where cig is not null
),

conteggi_file as (
    select
        cig,
        _risorsa,
        count(*) - count(distinct _hash_riga) as n_duplicati_esatti,
        count(distinct case when coalesce(flag_prevalente, false) then _hash_riga end) as n_righe_prevalenti
    from righe
    group by cig, _risorsa
),

scelta as (
    select
        *,
        row_number() over (
            partition by cig, _risorsa
            order by coalesce(flag_prevalente, false) desc, _hash_riga
        ) as _rn
    from righe
)

select
    {{ dbt_utils.generate_surrogate_key(['s.cig', 's._risorsa']) }} as versione_key,
    s.* exclude (_rn),
    c.n_duplicati_esatti,
    c.n_righe_prevalenti > 1 as flag_duplicato_conflittuale,
    count(*) over (partition by s.cig) as n_versioni,
    row_number() over (partition by s.cig order by s._data_snapshot desc, s._risorsa desc) as ordine_versione
from scelta as s
inner join conteggi_file as c
    on s.cig = c.cig and s._risorsa = c._risorsa
where s._rn = 1

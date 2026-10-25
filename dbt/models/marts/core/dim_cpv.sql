-- Codici CPV presi dai dati (riga prevalente dei lotti correnti) con la divisione dal seed.
with codici as (
    select
        cod_cpv,
        descrizione_cpv,
        divisione_cpv,
        row_number() over (partition by cod_cpv order by data_pubblicazione desc nulls last, cig) as _rn
    from {{ ref('int_cig__corrente') }}
    where cod_cpv is not null
)

select
    c.cod_cpv as cpv_key,
    c.cod_cpv,
    c.descrizione_cpv,
    c.divisione_cpv,
    d.descrizione_divisione
from codici as c
left join {{ ref('divisioni_cpv') }} as d on c.divisione_cpv = d.divisione_cpv
where c._rn = 1
union all
select 'ND', null, 'Non definito', null, null

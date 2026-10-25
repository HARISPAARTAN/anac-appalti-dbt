-- Procedure di scelta del contraente con la famiglia rivista (seed famiglie_procedura).
-- Codici assenti dal seed: famiglia 'altro', flag_mappata falso.
with vocabolario as (
    select
        cod_tipo_scelta_contraente,
        tipo_scelta_contraente,
        row_number() over (
            partition by cod_tipo_scelta_contraente order by _data_snapshot desc, _risorsa desc
        ) as _rn
    from {{ ref('stg_anac__tipi_scelta_contraente') }}
    where cod_tipo_scelta_contraente is not null
),

dai_lotti as (
    select
        cod_tipo_scelta_contraente,
        tipo_scelta_contraente,
        row_number() over (
            partition by cod_tipo_scelta_contraente order by data_pubblicazione desc nulls last, cig
        ) as _rn
    from {{ ref('int_cig__corrente') }}
    where cod_tipo_scelta_contraente is not null
),

codici as (
    select cod_tipo_scelta_contraente, tipo_scelta_contraente
    from vocabolario
    where _rn = 1
    union all
    select l.cod_tipo_scelta_contraente, l.tipo_scelta_contraente
    from dai_lotti as l
    where l._rn = 1
        and l.cod_tipo_scelta_contraente not in (select v.cod_tipo_scelta_contraente from vocabolario as v)
)

select
    c.cod_tipo_scelta_contraente as procedura_key,
    c.cod_tipo_scelta_contraente,
    c.tipo_scelta_contraente,
    coalesce(f.famiglia_procedura, 'altro') as famiglia_procedura,
    coalesce(f.famiglia_procedura, 'altro') in ('aperta', 'ristretta', 'negoziata con bando') as flag_competitiva,
    f.famiglia_procedura is not null as flag_mappata
from codici as c
left join {{ ref('famiglie_procedura') }} as f on c.cod_tipo_scelta_contraente = f.cod_tipo_scelta_contraente
union all
select 'ND', null, 'Non definita', 'altro', false, false

with base as (
    select
        famiglia_procedura,
        regione,
        anno,
        count(*) as n_lotti,
        coalesce(sum(importo_sommabile), 0) as importo_totale
    from {{ ref('int_radar__lotti') }}
    group by famiglia_procedura, regione, anno
)

select
    cast(famiglia_procedura as varchar) as famiglia_procedura,
    cast(regione as varchar) as regione,
    cast(anno as integer) as anno,
    cast(n_lotti as bigint) as n_lotti,
    cast(n_lotti / sum(n_lotti) over (partition by regione, anno) as double) as quota_lotti,
    cast(importo_totale as decimal(18, 2)) as importo_totale,
    cast(
        case
            when sum(importo_totale) over (partition by regione, anno) > 0
                then importo_totale / sum(importo_totale) over (partition by regione, anno)
        end as double
    ) as quota_importo
from base

select
    cast(divisione_cpv as varchar) as divisione_cpv,
    cast(descrizione_divisione as varchar) as descrizione_divisione,
    cast(anno as integer) as anno,
    cast(settore as varchar) as settore,
    cast(count(*) as bigint) as n_lotti,
    cast(coalesce(sum(importo_sommabile), 0) as decimal(18, 2)) as importo_totale,
    cast(avg(case when flag_affidamento_diretto then 1.0 else 0.0 end) as double) as quota_affidamento_diretto
from {{ ref('int_radar__lotti') }}
group by divisione_cpv, descrizione_divisione, anno, settore

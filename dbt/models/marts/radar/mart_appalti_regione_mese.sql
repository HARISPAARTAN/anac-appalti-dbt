select
    cast(regione as varchar) as regione,
    cast(mese as date) as mese,
    cast(anno as integer) as anno,
    cast(oggetto_principale_contratto as varchar) as oggetto_principale_contratto,
    cast(count(*) as bigint) as n_lotti,
    cast(coalesce(sum(importo_sommabile), 0) as decimal(18, 2)) as importo_totale,
    cast(median(importo_sommabile) as decimal(18, 2)) as importo_mediano,
    cast(avg(case when flag_pnrr_pnc then 1.0 else 0.0 end) as double) as quota_pnrr
from {{ ref('int_radar__lotti') }}
group by regione, mese, anno, oggetto_principale_contratto

-- Base: lotti aggiudicati. ANAC non pubblica importi di varianti e subappalti: si misurano le frequenze.
select
    cast(regione as varchar) as regione,
    cast(anno as integer) as anno,
    cast(count(*) as bigint) as n_lotti_aggiudicati,
    cast(avg(case when n_varianti > 0 then 1.0 else 0.0 end) as double) as quota_lotti_con_variante,
    cast(avg(n_varianti) as double) as varianti_per_lotto,
    cast(avg(case when flag_con_subappalto then 1.0 else 0.0 end) as double) as quota_subappalto
from {{ ref('int_radar__lotti') }}
where flag_aggiudicato
group by regione, anno

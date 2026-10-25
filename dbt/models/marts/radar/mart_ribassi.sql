select
    cast(famiglia_procedura as varchar) as famiglia_procedura,
    cast(oggetto_principale_contratto as varchar) as oggetto_principale_contratto,
    cast(anno as integer) as anno,
    cast(count(*) as bigint) as n_lotti,
    cast(median(ribasso_aggiudicazione) as double) as ribasso_mediano,
    cast(quantile_cont(ribasso_aggiudicazione, 0.1) as double) as ribasso_p10,
    cast(quantile_cont(ribasso_aggiudicazione, 0.9) as double) as ribasso_p90
from {{ ref('int_radar__lotti') }}
where ribasso_aggiudicazione is not null
group by famiglia_procedura, oggetto_principale_contratto, anno

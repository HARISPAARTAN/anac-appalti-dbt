select
    cast(regione as varchar) as regione,
    cast(famiglia_procedura as varchar) as famiglia_procedura,
    cast(mese as date) as mese,
    cast(anno as integer) as anno,
    cast(median(giorni_aggiudicazione) as double) as giorni_mediana,
    cast(quantile_cont(giorni_aggiudicazione, 0.9) as double) as giorni_p90,
    cast(count(*) as bigint) as n_validi
from {{ ref('int_radar__lotti') }}
where giorni_aggiudicazione is not null
group by regione, famiglia_procedura, mese, anno

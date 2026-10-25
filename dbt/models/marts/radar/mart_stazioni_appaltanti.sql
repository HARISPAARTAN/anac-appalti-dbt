select
    cast(stazione_key as varchar) as stazione_key,
    cast(codice_ausa as varchar) as codice_ausa,
    cast(denominazione_stazione as varchar) as denominazione,
    cast(regione_stazione as varchar) as regione,
    cast(anno as integer) as anno,
    cast(count(*) as bigint) as n_lotti,
    cast(coalesce(sum(importo_sommabile), 0) as decimal(18, 2)) as importo_totale,
    cast(avg(case when flag_affidamento_diretto then 1.0 else 0.0 end) as double) as quota_affidamento_diretto,
    cast(
        avg(case when n_offerte = 1 then 1.0 else 0.0 end) filter (where flag_competitiva and flag_aggiudicato and n_offerte > 0)
        as double
    ) as quota_offerta_unica
from {{ ref('int_radar__lotti') }}
group by stazione_key, codice_ausa, denominazione_stazione, regione_stazione, anno

-- Indicatore offerta unica (EU Single Market Scoreboard): procedure competitive aggiudicate con una sola offerta.
select
    cast(divisione_cpv as varchar) as divisione_cpv,
    cast(regione as varchar) as regione,
    cast(anno as integer) as anno,
    cast(count(*) as bigint) as n_lotti_competitivi_aggiudicati,
    cast(avg(n_offerte) as double) as offerte_medie,
    cast(avg(case when n_offerte = 1 then 1.0 else 0.0 end) as double) as quota_offerta_unica
from {{ ref('int_radar__lotti') }}
where flag_competitiva and flag_aggiudicato and n_offerte > 0
group by divisione_cpv, regione, anno

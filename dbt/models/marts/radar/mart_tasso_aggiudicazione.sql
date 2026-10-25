-- Lotti con scadenza offerte da almeno giorni_scadenza_tasso giorni (180) alla data di riferimento.
select
    cast(regione as varchar) as regione,
    cast(famiglia_procedura as varchar) as famiglia_procedura,
    cast(mese as date) as mese,
    cast(anno as integer) as anno,
    cast(count(*) as bigint) as n_lotti_scaduti,
    cast(count(*) filter (where flag_aggiudicato) as bigint) as n_aggiudicati,
    cast(count(*) filter (where flag_aggiudicato) / count(*) as double) as tasso_aggiudicazione
from {{ ref('int_radar__lotti') }}
where data_scadenza_offerta <= {{ data_riferimento() }} - to_days({{ var('giorni_scadenza_tasso') }})
group by regione, famiglia_procedura, mese, anno

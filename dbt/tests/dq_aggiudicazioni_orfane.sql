{{ config(severity='warn') }}
-- Avviso: aggiudicazioni il cui CIG non è nei dati CIG in ambito. Atteso per lotti pubblicati prima di anno_minimo.
select a.id_aggiudicazione, a.cig
from {{ ref('int_aggiudicazioni__corrente') }} as a
where not exists (
    select 1 from {{ ref('int_cig__versioni') }} as v where v.cig = a.cig
)

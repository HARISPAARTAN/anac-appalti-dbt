{{ config(severity='warn') }}
-- Avviso: lotto aggiudicato senza alcun aggiudicatario pubblicato.
select cig
from {{ ref('int_lotti__qualita') }}
where flag_senza_aggiudicatario

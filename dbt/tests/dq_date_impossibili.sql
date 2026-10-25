{{ config(severity='warn') }}
-- Avviso: scadenza o aggiudicazione prima della pubblicazione, date prima del 2007 o oltre due anni.
select cig
from {{ ref('int_lotti__qualita') }}
where flag_data_impossibile

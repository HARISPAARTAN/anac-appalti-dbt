{{ config(severity='warn') }}
-- Avviso: codice_ausa del lotto assente dall'anagrafe delle stazioni appaltanti.
select cig
from {{ ref('int_lotti__qualita') }}
where flag_stazione_orfana

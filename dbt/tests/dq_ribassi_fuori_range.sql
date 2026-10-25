{{ config(severity='warn') }}
-- Avviso: ribasso di aggiudicazione fuori dall'intervallo 0–100 %.
select id_aggiudicazione, cig, ribasso_aggiudicazione
from {{ ref('int_aggiudicazioni__corrente') }}
where ribasso_aggiudicazione < 0 or ribasso_aggiudicazione > 100

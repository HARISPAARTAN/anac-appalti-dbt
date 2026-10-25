{{ config(severity='warn') }}
-- Avviso: CIG con righe identiche ripetute nello stesso file (contate, tenuta una sola versione).
select cig, _risorsa, n_duplicati_esatti
from {{ ref('int_cig__versioni') }}
where n_duplicati_esatti > 0

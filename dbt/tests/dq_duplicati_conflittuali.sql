{{ config(severity='warn') }}
-- Avviso: stesso CIG con righe prevalenti diverse nello stesso file (vince l'ordine di _hash_riga).
select cig, _risorsa
from {{ ref('int_cig__versioni') }}
where flag_duplicato_conflittuale

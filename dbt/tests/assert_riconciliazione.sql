-- Errore: un file atterrato ha un numero di righe diverso da quello dichiarato da ANAC nel logCsv.
select tabella, risorsa, righe, righe_attese
from {{ ref('int_riconciliazione') }}
where riconciliazione = 'differenza'

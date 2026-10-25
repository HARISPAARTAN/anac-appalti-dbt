-- Errore: un file atterrato ha un numero di righe diverso da quello dichiarato da ANAC nel logCsv,
-- oppure è stato letto con righe scartate dal lettore tollerante (esito letto_con_scarti).
select tabella, risorsa, righe, righe_attese, riconciliazione, esito
from {{ ref('int_riconciliazione') }}
where riconciliazione = 'differenza' or esito = 'letto_con_scarti'

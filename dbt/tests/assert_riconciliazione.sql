-- Errore: un file atterrato ha un numero di righe diverso da quello dichiarato da ANAC nel logCsv (differenza)
-- o, se il logCsv non lo dichiara, dai record contati nel CSV (differenza_fisica), oppure è stato letto con righe scartate dal lettore tollerante (esito letto_con_scarti).
select tabella, risorsa, righe, righe_attese, riconciliazione, esito
from {{ ref('int_riconciliazione') }}
where riconciliazione in ('differenza', 'differenza_fisica') or esito = 'letto_con_scarti'

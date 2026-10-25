{{ config(severity='warn') }}
-- Avviso: importi non positivi, oltre il totale di gara, oltre 5 miliardi, non leggibili o anomali per MAD
-- (esclusi dalle somme).
select
    cig,
    flag_importo_non_positivo,
    flag_importo_oltre_gara,
    flag_importo_implausibile,
    flag_importo_non_leggibile,
    flag_importo_mad
from {{ ref('int_lotti__qualita') }}
where flag_importo_anomalo

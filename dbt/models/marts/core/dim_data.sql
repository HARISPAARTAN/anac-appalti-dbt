with giorni as (
    select cast(giorno as date) as data
    from range(timestamp '2007-01-01', timestamp '2031-01-01', interval 1 day) as t (giorno)
)

select
    {{ chiave_data('data') }} as data_key,
    data,
    cast(year(data) as integer) as anno,
    cast(quarter(data) as integer) as trimestre,
    cast(month(data) as integer) as mese,
    [
        'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
        'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'
    ][month(data)] as mese_esteso,
    strftime(data, '%Y-%m') as anno_mese,
    cast(day(data) as integer) as giorno,
    cast(isodow(data) as integer) as giorno_settimana,
    ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'][isodow(data)] as giorno_esteso,
    isodow(data) in (6, 7) as flag_fine_settimana
from giorni

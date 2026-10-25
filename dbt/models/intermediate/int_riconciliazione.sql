-- File atterrati e confronto con le righe dichiarate da ANAC nel logCsv.
select
    sha256,
    tabella,
    pacchetto,
    risorsa,
    try_cast(righe as bigint) as righe,
    try_cast(nullif(righe_attese, '') as bigint) as righe_attese,
    riconciliazione,
    esito,
    try_cast(data_snapshot as date) as data_snapshot,
    nullif(colonne_nuove, '') as colonne_nuove,
    coalesce(try_cast(nullif(cf_mascherati, '') as bigint), 0) as n_cf_mascherati
from {{ source('landing_meta', 'registro') }}
where esito in ('atterrato', 'letto_con_scarti')

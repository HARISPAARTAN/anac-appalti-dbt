-- Una riga per persona giuridica (codice di 11 cifre); denominazione dall'occorrenza più recente.
-- Le ditte individuali (tipo_soggetto individuale in qualunque occorrenza) hanno il nome annullato: il loro nome e
-- la loro partita IVA sono dati personali, il codice resta come chiave locale (conteggi di operatori distinti).
with occorrenze as (
    select codice_fiscale, denominazione, flag_ditta_individuale, _data_snapshot, _risorsa
    from {{ ref('int_aggiudicatari__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select codice_fiscale, denominazione, flag_ditta_individuale, _data_snapshot, _risorsa
    from {{ ref('int_partecipanti__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select codice_fiscale, denominazione, flag_ditta_individuale, _data_snapshot, _risorsa
    from {{ ref('int_subappalti__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select cf_subappaltante, null, false, _data_snapshot, _risorsa
    from {{ ref('int_subappalti__corrente') }}
    where tipo_subappaltante_privacy = 'persona_giuridica'
),

ordinate as (
    select
        *,
        count(*) over (partition by codice_fiscale) as n_occorrenze,
        bool_or(flag_ditta_individuale) over (partition by codice_fiscale) as _ditta_individuale,
        row_number() over (
            partition by codice_fiscale
            order by _data_snapshot desc, _risorsa desc, denominazione nulls last
        ) as _rn
    from occorrenze
)

select
    codice_fiscale,
    case when not _ditta_individuale then denominazione end as denominazione,
    _ditta_individuale as flag_ditta_individuale,
    n_occorrenze,
    _data_snapshot as data_ultima_occorrenza
from ordinate
where _rn = 1

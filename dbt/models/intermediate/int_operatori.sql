-- Una riga per persona giuridica (codice di 11 cifre); denominazione dall'occorrenza più recente.
with occorrenze as (
    select codice_fiscale, denominazione, _data_snapshot, _risorsa
    from {{ ref('int_aggiudicatari__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select codice_fiscale, denominazione, _data_snapshot, _risorsa
    from {{ ref('int_partecipanti__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select codice_fiscale, denominazione, _data_snapshot, _risorsa
    from {{ ref('int_subappalti__corrente') }}
    where tipo_soggetto_privacy = 'persona_giuridica'
    union all
    select cf_subappaltante, null, _data_snapshot, _risorsa
    from {{ ref('int_subappalti__corrente') }}
    where tipo_subappaltante_privacy = 'persona_giuridica'
),

ordinate as (
    select
        *,
        count(*) over (partition by codice_fiscale) as n_occorrenze,
        row_number() over (
            partition by codice_fiscale
            order by _data_snapshot desc, _risorsa desc, denominazione nulls last
        ) as _rn
    from occorrenze
)

select
    codice_fiscale,
    denominazione,
    n_occorrenze,
    _data_snapshot as data_ultima_occorrenza
from ordinate
where _rn = 1

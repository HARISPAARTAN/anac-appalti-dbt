with sorgente as (
    select * from {{ source('anac', 'stazioni_appaltanti') }}
)

select
    {{ codice('codice_fiscale') }} as codice_fiscale,
    nullif({{ codice('partita_iva') }}, '00000000000') as partita_iva,
    {{ testo('denominazione') }} as denominazione,
    {{ codice('codice_ausa') }} as codice_ausa,
    {{ codice_numerico('natura_giuridica_codice') }} as natura_giuridica_codice,
    {{ testo('natura_giuridica_descrizione') }} as natura_giuridica_descrizione,
    {{ parse_flag('soggetto_estero') }} as flag_soggetto_estero,
    case
        when regexp_full_match({{ codice('provincia_codice') }}, 'IT-[A-Z]{2}') then right({{ codice('provincia_codice') }}, 2)
    end as sigla_provincia,
    {{ codice('provincia') }} as provincia,
    {{ codice('codice_comune') }} as codice_comune,
    case
        when regexp_full_match({{ codice('codice_comune') }}, '[0-9]{6}') then left({{ codice('codice_comune') }}, 3)
    end as codice_provincia,
    {{ testo('comune') }} as comune,
    {{ parse_flag('flag_inhouse') }} as flag_inhouse,
    {{ parse_flag('flag_partecipata') }} as flag_partecipata,
    {{ codice('stato') }} as stato,
    {{ parse_data_it('data_inizio') }} as data_inizio,
    {{ parse_data_it('data_fine') }} as data_fine,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga
from sorgente

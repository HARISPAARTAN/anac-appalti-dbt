-- Regola persone fisiche anche per le stazioni appaltanti: l'anagrafe contiene ditte individuali, liberi
-- professionisti e lavoratori autonomi, con il codice fiscale personale e il nome della persona. Una stazione è
-- una persona fisica se il codice fiscale è di 16 caratteri o se la forma giuridica dice che è un individuo
-- (macro stazione_persona_fisica): codice fiscale, partita IVA, comune e denominazione vengono annullati
-- (denominazione: dicitura anonima) e `flag_persona_fisica` resta. Il codice AUSA (identificativo opaco) resta
-- solo in questo strato locale: i mart non lo pubblicano per le persone fisiche.
with sorgente as (
    select
        * replace (
            {{ codice('codice_fiscale') }} as codice_fiscale,
            nullif({{ codice('partita_iva') }}, '00000000000') as partita_iva,
            {{ testo('denominazione') }} as denominazione,
            {{ codice('codice_ausa') }} as codice_ausa,
            {{ codice_numerico('natura_giuridica_codice') }} as natura_giuridica_codice,
            {{ testo('natura_giuridica_descrizione') }} as natura_giuridica_descrizione
        )
    from {{ source('anac', 'stazioni_appaltanti') }}
),

classificata as (
    select
        *,
        {{ stazione_persona_fisica('codice_fiscale', 'natura_giuridica_codice', 'natura_giuridica_descrizione') }}
            or {{ contiene_cf_persona('denominazione') }}
            or codice_ausa in (select upper(trim(codice_ausa)) from {{ ref('ausa_persone_fisiche') }}) as flag_persona_fisica
    from sorgente
)

select
    case when not flag_persona_fisica then codice_fiscale end as codice_fiscale,
    case when not flag_persona_fisica then partita_iva end as partita_iva,
    case when flag_persona_fisica then 'Persona fisica (identità non pubblicata)' else denominazione end
        as denominazione,
    flag_persona_fisica,
    codice_ausa,
    natura_giuridica_codice,
    natura_giuridica_descrizione,
    {{ parse_flag('soggetto_estero') }} as flag_soggetto_estero,
    case
        when regexp_full_match({{ codice('provincia_codice') }}, 'IT-[A-Z]{2}') then right({{ codice('provincia_codice') }}, 2)
    end as sigla_provincia,
    {{ codice('provincia') }} as provincia,
    {{ codice('codice_comune') }} as codice_comune,
    case
        when regexp_full_match({{ codice('codice_comune') }}, '[0-9]{6}') then left({{ codice('codice_comune') }}, 3)
    end as codice_provincia,
    case when not flag_persona_fisica then {{ testo('comune') }} end as comune,
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
from classificata

-- Stazioni appaltanti che potrebbero essere persone fisiche e che le regole non vedono: codice non di 11 cifre (nel
-- registro sono i segnaposto CFAVCP-…), forma giuridica "non classificato", "non definito" o assente, nome di 2-3
-- parole senza cifre e senza parole di ente. Nei dati reali la classe nasconde nomi e cognomi di persone. Ogni
-- candidato si legge a mano (la tabella di audit del test assert_candidati_stazioni_classificati mostra il nome) e
-- finisce in ausa_persone_fisiche (persona) o in ausa_enti_verificati (ente): finché ne manca uno, il test fallisce.
-- Una stazione già riconosciuta come persona (flag_persona_fisica) non è candidata.
with base as (
    select
        codice_ausa,
        codice_fiscale,
        natura_giuridica_descrizione,
        denominazione,
        list_transform(regexp_extract_all(denominazione, '\p{L}+'), p -> upper(strip_accents(p))) as parole
    from {{ ref('stg_anac__stazioni_appaltanti') }}
    where not flag_persona_fisica
        and codice_ausa is not null
        and (codice_fiscale is null or not regexp_full_match(codice_fiscale, '[0-9]{11}'))
        and (natura_giuridica_descrizione is null or upper(natura_giuridica_descrizione) in ('NON CLASSIFICATO', 'NON DEFINITO'))
        and denominazione is not null
        and not regexp_matches(denominazione, '[0-9]')
)

select codice_ausa, codice_fiscale, natura_giuridica_descrizione, denominazione, len(parole) as n_parole
from base
where len(parole) between 2 and 3
    and not list_has_any(parole, {{ parole_ente() }})

-- Una riga per codice AUSA: le stazioni dell'anagrafe, più quelle che compaiono nei lotti ma non in anagrafe.
-- Regola persone fisiche: una stazione che è una persona fisica (codice fiscale di 16 caratteri o forma giuridica
-- individuale; per le assenti dall'anagrafe, il codice fiscale del lotto) non ha chiave propria: `stazione_key` è
-- 'PERSONA_FISICA' per tutte, il nome è la dicitura anonima e non resta alcun attributo identificativo.
with anagrafe as (
    select
        *,
        row_number() over (
            partition by codice_ausa
            order by (stato = 'ATTIVO') desc nulls last, data_inizio desc nulls last, codice_fiscale, _hash_riga
        ) as _rn
    from {{ ref('stg_anac__stazioni_appaltanti') }}
    where codice_ausa is not null
),

registrate as (
    select
        codice_ausa,
        codice_fiscale,
        denominazione,
        natura_giuridica_descrizione,
        codice_provincia,
        flag_persona_fisica,
        true as flag_in_anagrafe
    from anagrafe
    where _rn = 1
),

dai_lotti as (
    select
        codice_ausa,
        cf_amministrazione_appaltante as codice_fiscale,
        denominazione_amministrazione_appaltante as denominazione,
        bool_or(flag_amministrazione_persona_fisica) over (partition by codice_ausa) as flag_persona_fisica,
        row_number() over (partition by codice_ausa order by data_pubblicazione desc nulls last, cig) as _rn
    from {{ ref('int_cig__corrente') }}
    where codice_ausa is not null
),

orfane as (
    select
        l.codice_ausa,
        l.codice_fiscale,
        l.denominazione,
        cast(null as varchar) as natura_giuridica_descrizione,
        cast(null as varchar) as codice_provincia,
        l.flag_persona_fisica,
        false as flag_in_anagrafe
    from dai_lotti as l
    left join registrate as r on l.codice_ausa = r.codice_ausa
    where l._rn = 1 and r.codice_ausa is null
)

select
    case when flag_persona_fisica then 'PERSONA_FISICA' else codice_ausa end as stazione_key,
    codice_ausa,
    case when flag_persona_fisica then null else codice_fiscale end as codice_fiscale,
    case when flag_persona_fisica then 'Persona fisica (identità non pubblicata)' else denominazione end as denominazione,
    case when flag_persona_fisica then null else natura_giuridica_descrizione end as natura_giuridica_descrizione,
    case when flag_persona_fisica then null else codice_provincia end as codice_provincia,
    flag_persona_fisica,
    flag_in_anagrafe
from (
    select * from registrate
    union all
    select * from orfane
)

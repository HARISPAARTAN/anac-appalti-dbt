-- Stazioni appaltanti dall'anagrafe AUSA, più quelle che compaiono nei lotti ma non in anagrafe.
with anagrafe as (
    select
        *,
        row_number() over (
            partition by codice_ausa
            order by (stato = 'ATTIVO') desc nulls last, data_inizio desc nulls last, codice_fiscale
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
        true as flag_in_anagrafe
    from anagrafe
    where _rn = 1
),

dai_lotti as (
    select
        codice_ausa,
        cf_amministrazione_appaltante as codice_fiscale,
        denominazione_amministrazione_appaltante as denominazione,
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
        false as flag_in_anagrafe
    from dai_lotti as l
    left join registrate as r on l.codice_ausa = r.codice_ausa
    where l._rn = 1 and r.codice_ausa is null
),

tutte as (
    select * from registrate
    union all
    select * from orfane
)

select
    t.codice_ausa as stazione_key,
    t.codice_ausa,
    t.codice_fiscale,
    t.denominazione,
    t.natura_giuridica_descrizione,
    t.codice_provincia,
    p.provincia,
    coalesce(p.regione, 'Non definita') as regione,
    p.nuts2,
    t.flag_in_anagrafe
from tutte as t
left join {{ ref('regioni_province') }} as p on t.codice_provincia = p.codice_provincia
union all
select 'ND', null, null, 'Non definita', null, null, null, 'Non definita', null, false

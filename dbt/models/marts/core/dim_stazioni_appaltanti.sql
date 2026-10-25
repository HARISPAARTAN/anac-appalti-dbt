-- Stazioni appaltanti dall'anagrafe AUSA, più quelle che compaiono nei lotti ma non in anagrafe (int_stazioni).
-- Le persone fisiche (ditte individuali, liberi professionisti, lavoratori autonomi) sono un solo membro anonimo,
-- come per gli operatori: nessun codice AUSA, codice fiscale o nome.
select
    t.stazione_key,
    t.codice_ausa,
    t.codice_fiscale,
    t.denominazione,
    t.natura_giuridica_descrizione,
    t.codice_provincia,
    p.provincia,
    coalesce(p.regione, 'Non definita') as regione,
    p.nuts2,
    t.flag_in_anagrafe
from {{ ref('int_stazioni') }} as t
left join {{ ref('regioni_province') }} as p on t.codice_provincia = p.codice_provincia
where not t.flag_persona_fisica
union all
select 'PERSONA_FISICA', null, null, 'Persona fisica (identità non pubblicata)', null, null, null, 'Non definita', null, false
union all
select 'ND', null, null, 'Non definita', null, null, null, 'Non definita', null, false

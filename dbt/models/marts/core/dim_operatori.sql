-- Solo persone giuridiche; persone fisiche e codici non verificabili sono due membri anonimi.
select
    codice_fiscale as operatore_key,
    codice_fiscale,
    denominazione,
    'persona_giuridica' as tipo_soggetto_privacy,
    n_occorrenze
from {{ ref('int_operatori') }}
union all
select 'PERSONA_FISICA', null, 'Persona fisica (identità non pubblicata)', 'persona_fisica', null
union all
select 'NON_VERIFICABILE', null, 'Codice non verificabile o assente', 'non_verificabile', null

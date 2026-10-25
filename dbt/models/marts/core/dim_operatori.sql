-- Solo persone giuridiche con codice di 11 cifre; persone fisiche e codici non verificabili sono due membri anonimi.
-- Le ditte individuali (flag_ditta_individuale) tengono il codice come chiave locale ma il nome è la dicitura
-- anonima: nessun mart pubblicato porta nomi di operatori.
select
    codice_fiscale as operatore_key,
    codice_fiscale,
    case
        when flag_ditta_individuale then 'Persona fisica (identità non pubblicata)'
        else denominazione
    end as denominazione,
    flag_ditta_individuale,
    'persona_giuridica' as tipo_soggetto_privacy,
    n_occorrenze
from {{ ref('int_operatori') }}
union all
select 'PERSONA_FISICA', null, 'Persona fisica (identità non pubblicata)', false, 'persona_fisica', null
union all
select 'NON_VERIFICABILE', null, 'Codice non verificabile o assente', false, 'non_verificabile', null

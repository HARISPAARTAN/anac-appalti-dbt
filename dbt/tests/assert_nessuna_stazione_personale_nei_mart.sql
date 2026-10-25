-- Errore: una chiave del mart delle stazioni appaltanti corrisponde, nell'anagrafe o nei lotti, a una persona fisica.
-- Il confronto è per join sulla sorgente (landing), non su un modello della catena: una persona fisica è una
-- stazione con codice fiscale di 16 caratteri o con forma giuridica individuale (macro stazione_persona_fisica),
-- oppure, se assente dall'anagrafe, con il codice fiscale personale nei lotti. Nessuna chiave del mart deve
-- corrispondere: le persone fisiche sono il solo membro anonimo PERSONA_FISICA. Un test sui nomi non basta.
with personali as (
    select codice_ausa, 'anagrafe' as origine from ({{ ausa_stazioni_personali() }})
    union all
    select upper(trim(codice_ausa)), 'lotti'
    from {{ source('anac', 'cig') }}
    where upper(trim(codice_ausa)) is not null
        and regexp_full_match(
            upper(trim(cf_amministrazione_appaltante)),
            '[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]'
        )
)

select distinct m.stazione_key, m.codice_ausa, p.origine
from {{ ref('mart_stazioni_appaltanti') }} as m
inner join personali as p on p.codice_ausa = m.stazione_key or p.codice_ausa = m.codice_ausa

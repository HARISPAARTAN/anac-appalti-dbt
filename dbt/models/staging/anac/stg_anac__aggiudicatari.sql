-- Regola persone fisiche: identità tenuta solo per codici di 11 cifre (persona_giuridica).
-- Il landing ha già annullato i codici personali; qui si riapplica la regola e non si ricostruisce nulla.
with sorgente as (
    select
        *,
        {{ classifica_cf('codice_fiscale') }} as classe_codice_presente
    from {{ source('anac', 'aggiudicatari') }}
),

classificata as (
    select
        *,
        {{ classe_privacy('classe_codice_presente', '_classe_cf') }} as tipo_soggetto_privacy
    from sorgente
)

select
    {{ codice('cig') }} as cig,
    {{ codice('ruolo') }} as ruolo,
    case when classe_codice_presente = 'persona_giuridica' then trim(codice_fiscale) end as codice_fiscale,
    case when classe_codice_presente = 'persona_giuridica' and not {{ contiene_cf_persona('denominazione') }}
        then {{ testo('denominazione') }} end as denominazione,
    {{ codice('tipo_soggetto') }} as tipo_soggetto,
    tipo_soggetto_privacy,
    nullif({{ parse_intero('id_aggiudicazione') }}, -1) as id_aggiudicazione,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga,
    _ordinale_riga
from classificata

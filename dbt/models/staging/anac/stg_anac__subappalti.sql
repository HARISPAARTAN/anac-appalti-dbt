-- Regola persone fisiche su subappaltatore (codice_fiscale) e su subappaltante (cf_subappaltante).
-- Il landing ha già annullato i codici personali; qui si riapplica la regola e non si ricostruisce nulla.
with sorgente as (
    select
        *,
        {{ classifica_cf('codice_fiscale') }} as classe_codice_presente,
        {{ classifica_cf('cf_subappaltante') }} as classe_subappaltante_presente
    from {{ source('anac', 'subappalti') }}
),

classificata as (
    select
        *,
        {{ classe_privacy('classe_codice_presente', '_classe_cf') }} as tipo_soggetto_privacy,
        {{ classe_privacy('classe_subappaltante_presente', '_classe_cf_subappaltante') }} as tipo_subappaltante_privacy
    from sorgente
)

select
    {{ codice('cig') }} as cig,
    {{ testo('id_subappalto') }} as id_subappalto,
    case when classe_subappaltante_presente = 'persona_giuridica' then trim(cf_subappaltante) end as cf_subappaltante,
    tipo_subappaltante_privacy,
    {{ parse_data_it('data_autorizzazione') }} as data_autorizzazione,
    {{ testo('oggetto') }} as oggetto,
    {{ codice('cod_categoria') }} as cod_categoria,
    {{ testo('descrizione_categoria') }} as descrizione_categoria,
    {{ codice('classe_importo') }} as classe_importo,
    {{ codice('descrizione_tipo_categoria') }} as descrizione_tipo_categoria,
    {{ codice('cod_cpv') }} as cod_cpv,
    {{ testo('descrizione_cpv') }} as descrizione_cpv,
    case when classe_codice_presente = 'persona_giuridica' then trim(codice_fiscale) end as codice_fiscale,
    case when classe_codice_presente = 'persona_giuridica' then {{ testo('denominazione') }} end as denominazione,
    {{ codice('ruolo') }} as ruolo,
    {{ codice('tipo_soggetto') }} as tipo_soggetto,
    tipo_soggetto_privacy,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga,
    _ordinale_riga
from classificata

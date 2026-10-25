with sorgente as (
    select * from {{ source('anac', 'cig') }}
)

select
    {{ codice('cig') }} as cig,
    {{ codice('cig_accordo_quadro') }} as cig_accordo_quadro,
    {{ testo('numero_gara') }} as numero_gara,
    {{ testo('oggetto_gara') }} as oggetto_gara,
    {{ parse_importo('importo_complessivo_gara') }} as importo_complessivo_gara,
    {{ parse_intero('n_lotti_componenti') }} as n_lotti_componenti,
    {{ testo('oggetto_lotto') }} as oggetto_lotto,
    {{ parse_importo('importo_lotto') }} as importo_lotto,
    {{ codice('oggetto_principale_contratto') }} as oggetto_principale_contratto,
    {{ codice('stato') }} as stato,
    {{ codice('settore') }} as settore,
    {{ codice('luogo_istat') }} as luogo_istat,
    case
        when regexp_full_match({{ codice('luogo_istat') }}, '[0-9]{6}') then left({{ codice('luogo_istat') }}, 3)
    end as codice_provincia,
    {{ codice('provincia') }} as provincia,
    {{ parse_data_it('data_pubblicazione') }} as data_pubblicazione,
    {{ parse_data_it('data_scadenza_offerta') }} as data_scadenza_offerta,
    {{ codice_numerico('cod_tipo_scelta_contraente') }} as cod_tipo_scelta_contraente,
    {{ codice('tipo_scelta_contraente') }} as tipo_scelta_contraente,
    {{ codice_numerico('cod_modalita_realizzazione') }} as cod_modalita_realizzazione,
    {{ codice('modalita_realizzazione') }} as modalita_realizzazione,
    {{ codice('codice_ausa') }} as codice_ausa,
    {{ codice('cf_amministrazione_appaltante') }} as cf_amministrazione_appaltante,
    {{ testo('denominazione_amministrazione_appaltante') }} as denominazione_amministrazione_appaltante,
    {{ codice('sezione_regionale') }} as sezione_regionale,
    {{ codice('cod_cpv') }} as cod_cpv,
    case
        when regexp_matches({{ codice('cod_cpv') }}, '^[0-9]{2}') then left({{ codice('cod_cpv') }}, 2)
    end as divisione_cpv,
    {{ testo('descrizione_cpv') }} as descrizione_cpv,
    {{ parse_flag('flag_prevalente') }} as flag_prevalente,
    {{ codice_numerico('cod_motivo_cancellazione') }} as cod_motivo_cancellazione,
    {{ testo('motivo_cancellazione') }} as motivo_cancellazione,
    {{ parse_data_it('data_cancellazione') }} as data_cancellazione,
    {{ parse_data_it('data_ultimo_perfezionamento') }} as data_ultimo_perfezionamento,
    {{ parse_intero('durata_prevista') }} as durata_prevista,
    {{ parse_flag('flag_urgenza') }} as flag_urgenza,
    {{ parse_importo('importo_sicurezza') }} as importo_sicurezza,
    {{ parse_intero('cod_esito') }} as cod_esito,
    {{ codice('esito') }} as esito,
    {{ parse_data_it('data_comunicazione_esito') }} as data_comunicazione_esito,
    {{ parse_flag('flag_pnrr_pnc') }} as flag_pnrr_pnc,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga
from sorgente

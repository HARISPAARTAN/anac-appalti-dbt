with sorgente as (
    select * from {{ source('anac', 'varianti') }}
)

select
    {{ parse_intero('id_variante') }} as id_variante,
    {{ codice_numerico('cod_motivo_variante') }} as cod_motivo_variante,
    {{ testo('motivo_variante') }} as motivo_variante,
    {{ parse_data_it('data_approvazione_variante') }} as data_approvazione_variante,
    {{ codice('cig') }} as cig,
    nullif({{ parse_intero('id_aggiudicazione') }}, -1) as id_aggiudicazione,
    {{ codice('cig_proroga') }} as cig_proroga,
    {{ parse_data_it('data_atto_aggiuntivo') }} as data_atto_aggiuntivo,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga
from sorgente

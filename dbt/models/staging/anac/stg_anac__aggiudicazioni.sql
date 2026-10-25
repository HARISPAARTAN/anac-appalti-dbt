with sorgente as (
    select * from {{ source('anac', 'aggiudicazioni') }}
)

select
    {{ codice('cig') }} as cig,
    {{ parse_data_it('data_aggiudicazione_definitiva') }} as data_aggiudicazione_definitiva,
    {{ codice('esito') }} as esito,
    {{ codice('criterio_aggiudicazione') }} as criterio_aggiudicazione,
    {{ parse_data_it('data_comunicazione_esito') }} as data_comunicazione_esito,
    {{ parse_intero('numero_offerte_ammesse') }} as n_offerte_ammesse,
    {{ parse_intero('numero_offerte_escluse') }} as n_offerte_escluse,
    {{ parse_importo('importo_aggiudicazione') }} as importo_aggiudicazione,
    try_cast(replace(nullif(trim(ribasso_aggiudicazione), ''), ',', '.') as double) as ribasso_aggiudicazione,
    {{ parse_intero('num_imprese_offerenti') }} as n_imprese_offerenti,
    {{ parse_flag('flag_subappalto') }} as flag_subappalto,
    {{ parse_intero('id_aggiudicazione') }} as id_aggiudicazione,
    {{ parse_intero('cod_esito') }} as cod_esito,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga
from sorgente

with sorgente as (
    select * from {{ source('anac', 'tipi_scelta_contraente') }}
)

select
    {{ codice_numerico('cod_tipo_scelta_contraente') }} as cod_tipo_scelta_contraente,
    {{ codice('tipo_scelta_contraente') }} as tipo_scelta_contraente,
    _risorsa,
    _data_snapshot,
    _caricato_il,
    _sha256,
    _hash_riga
from sorgente

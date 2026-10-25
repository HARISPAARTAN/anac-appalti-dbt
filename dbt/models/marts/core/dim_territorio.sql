select
    codice_provincia as territorio_key,
    codice_provincia,
    sigla_provincia,
    provincia,
    codice_regione,
    regione,
    nuts2
from {{ ref('regioni_province') }}
union all
select 'ND', null, null, 'Non definita', null, 'Non definita', null

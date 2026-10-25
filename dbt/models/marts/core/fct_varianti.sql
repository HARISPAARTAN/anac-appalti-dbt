-- Grana: variante di un lotto in ambito. ANAC non pubblica importi delle varianti.
select
    v.id_variante,
    v.cig,
    v.id_aggiudicazione,
    v.cod_motivo_variante,
    v.motivo_variante,
    v.data_approvazione_variante,
    {{ chiave_data('v.data_approvazione_variante') }} as data_approvazione_key,
    v.cig_proroga,
    v.data_atto_aggiuntivo
from {{ ref('int_varianti__corrente') }} as v
inner join {{ ref('fct_lotti') }} as l on v.cig = l.cig

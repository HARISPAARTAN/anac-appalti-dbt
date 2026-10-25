-- Grana: subappalto autorizzato di un lotto in ambito. ANAC pubblica solo la classe di importo.
select
    s.id_subappalto,
    s.cig,
    s.data_autorizzazione,
    {{ chiave_data('s.data_autorizzazione') }} as data_autorizzazione_key,
    s.cod_categoria,
    s.descrizione_categoria,
    s.classe_importo,
    s.descrizione_tipo_categoria,
    s.cod_cpv,
    {{ chiave_operatore('s.tipo_soggetto_privacy', 's.codice_fiscale') }} as operatore_key,
    {{ chiave_operatore('s.tipo_subappaltante_privacy', 's.cf_subappaltante') }} as subappaltante_key
from {{ ref('int_subappalti__corrente') }} as s
inner join {{ ref('fct_lotti') }} as l on s.cig = l.cig

-- Grana: aggiudicazione corrente di un lotto in ambito.
-- giorni_pubblicazione_aggiudicazione solo per coppie di date valide.
with lotti as (
    select cig, data_pubblicazione, flag_data_impossibile
    from {{ ref('fct_lotti') }}
)

select
    a.id_aggiudicazione,
    a.cig,
    {{ chiave_data('a.data_aggiudicazione_definitiva') }} as data_aggiudicazione_key,
    a.data_aggiudicazione_definitiva,
    a.esito,
    a.criterio_aggiudicazione,
    a.importo_aggiudicazione,
    a.ribasso_aggiudicazione,
    a.n_offerte_ammesse,
    coalesce(a.n_offerte_ammesse, a.n_imprese_offerenti) as n_offerte,
    case
        when not l.flag_data_impossibile and a.data_aggiudicazione_definitiva >= l.data_pubblicazione
            then date_diff('day', l.data_pubblicazione, a.data_aggiudicazione_definitiva)
    end as giorni_pubblicazione_aggiudicazione,
    coalesce(a.ribasso_aggiudicazione < 0 or a.ribasso_aggiudicazione > 100, false) as flag_ribasso_fuori_range,
    a.flag_subappalto
from {{ ref('int_aggiudicazioni__corrente') }} as a
inner join lotti as l on a.cig = l.cig

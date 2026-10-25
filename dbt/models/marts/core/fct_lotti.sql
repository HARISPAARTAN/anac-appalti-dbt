-- Grana: CIG (versione corrente). Le somme di importo usano solo flag_importo_sommabile.
with lotti as (
    select * from {{ ref('int_cig__corrente') }}
),

qualita as (
    select * from {{ ref('int_lotti__qualita') }}
),

accordi_quadro as (
    select distinct cig_accordo_quadro as cig
    from lotti
    where cig_accordo_quadro is not null
),

province as (
    select codice_provincia from {{ ref('regioni_province') }}
),

base as (
    select
        l.cig,
        {{ chiave_data('l.data_pubblicazione') }} as data_pubblicazione_key,
        coalesce(l.codice_ausa, 'ND') as stazione_key,
        coalesce(p.codice_provincia, 'ND') as territorio_key,
        coalesce(l.cod_cpv, 'ND') as cpv_key,
        coalesce(l.cod_tipo_scelta_contraente, 'ND') as procedura_key,
        coalesce(l.settore, 'ND') as settore,
        coalesce(l.oggetto_principale_contratto, 'ND') as oggetto_principale_contratto,
        l.numero_gara,
        l.cig_accordo_quadro,
        l.stato,
        l.esito,
        l.data_pubblicazione,
        l.data_scadenza_offerta,
        l.importo_lotto,
        l.importo_complessivo_gara,
        coalesce(l.stato = 'CANCELLATO' or l.data_cancellazione is not null, false) as flag_annullato,
        coalesce(l.cod_tipo_scelta_contraente = '16', false) or a.cig is not null as flag_accordo_quadro,
        l.cig_accordo_quadro is not null as flag_derivato_da_accordo_quadro,
        coalesce(l.flag_pnrr_pnc, false) as flag_pnrr_pnc,
        q.flag_duplicato_esatto,
        q.flag_duplicato_conflittuale,
        q.flag_data_impossibile,
        q.flag_importo_anomalo,
        q.flag_importo_non_leggibile,
        q.flag_aggiudicazione_non_leggibile,
        q.flag_senza_aggiudicatario,
        q.flag_stazione_orfana,
        q.flag_ribasso_fuori_range,
        l.n_versioni,
        l._data_snapshot as data_snapshot
    from lotti as l
    inner join qualita as q on l.cig = q.cig
    left join accordi_quadro as a on l.cig = a.cig
    left join province as p on l.codice_provincia = p.codice_provincia
)

select
    *,
    importo_lotto is not null
    and not flag_derivato_da_accordo_quadro
    and not flag_importo_anomalo
    and not flag_annullato as flag_importo_sommabile
from base

-- Preparazione dei mart Radar: un lotto per riga con tutti gli attributi delle dimensioni.
-- Esclusi i lotti cancellati e quelli senza data di pubblicazione. Contano solo le aggiudicazioni con esito
-- aggiudicata (flag_esito_aggiudicato); l'ultima per data e id guida n_offerte e ribasso.
with lotti as (
    select * from {{ ref('fct_lotti') }}
    where not flag_annullato and data_pubblicazione is not null
),

ultima_aggiudicazione as (
    select
        *,
        row_number() over (
            partition by cig order by data_aggiudicazione_definitiva desc nulls last, id_aggiudicazione desc
        ) as _rn
    from {{ ref('fct_aggiudicazioni') }}
    where flag_esito_aggiudicato
),

tempi as (
    select cig, min(giorni_pubblicazione_aggiudicazione) as giorni_aggiudicazione
    from {{ ref('fct_aggiudicazioni') }}
    where flag_esito_aggiudicato
    group by cig
),

varianti as (
    select cig, count(*) as n_varianti
    from {{ ref('fct_varianti') }}
    group by cig
),

subappalti as (
    select distinct cig from {{ ref('fct_subappalti') }}
)

select
    l.cig,
    cast(year(l.data_pubblicazione) as integer) as anno,
    cast(date_trunc('month', l.data_pubblicazione) as date) as mese,
    t.regione,
    t.nuts2,
    coalesce(c.divisione_cpv, 'ND') as divisione_cpv,
    coalesce(c.descrizione_divisione, 'Non definita') as descrizione_divisione,
    l.settore,
    l.oggetto_principale_contratto,
    p.famiglia_procedura,
    p.flag_competitiva,
    p.famiglia_procedura = 'affidamento diretto' as flag_affidamento_diretto,
    l.stazione_key,
    s.codice_ausa,
    s.denominazione as denominazione_stazione,
    s.regione as regione_stazione,
    l.importo_lotto,
    case when l.flag_importo_sommabile then l.importo_lotto end as importo_sommabile,
    l.flag_pnrr_pnc,
    l.data_scadenza_offerta,
    u.cig is not null as flag_aggiudicato,
    tm.giorni_aggiudicazione,
    u.n_offerte,
    case when not u.flag_ribasso_fuori_range then u.ribasso_aggiudicazione end as ribasso_aggiudicazione,
    coalesce(v.n_varianti, 0) as n_varianti,
    sa.cig is not null as flag_con_subappalto
from lotti as l
inner join {{ ref('dim_territorio') }} as t on l.territorio_key = t.territorio_key
inner join {{ ref('dim_cpv') }} as c on l.cpv_key = c.cpv_key
inner join {{ ref('dim_procedure') }} as p on l.procedura_key = p.procedura_key
inner join {{ ref('dim_stazioni_appaltanti') }} as s on l.stazione_key = s.stazione_key
left join ultima_aggiudicazione as u on l.cig = u.cig and u._rn = 1
left join tempi as tm on l.cig = tm.cig
left join varianti as v on l.cig = v.cig
left join subappalti as sa on l.cig = sa.cig

-- Una riga per lotto corrente con tutti i flag di qualità (sezione 9 della specifica).
-- Politica: si segnala, non si cancella. flag_importo_anomalo esclude il lotto dalle somme.
-- Un importo che non si legge (formato sconosciuto, oltre decimal(18,2)) non diventa un NULL silenzioso:
-- il testo originale resta in *_raw e il lotto è segnalato da flag_importo_non_leggibile.
with lotti as (
    select * from {{ ref('int_cig__corrente') }}
),

storia as (
    select
        cig,
        bool_or(n_duplicati_esatti > 0) as flag_duplicato_esatto,
        bool_or(flag_duplicato_conflittuale) as flag_duplicato_conflittuale
    from {{ ref('int_cig__versioni') }}
    group by cig
),

aggiudicazioni as (
    select
        cig,
        min(data_aggiudicazione_definitiva) as data_aggiudicazione,
        bool_or(ribasso_aggiudicazione < 0 or ribasso_aggiudicazione > 100) as flag_ribasso_fuori_range,
        bool_or(
            (importo_aggiudicazione is null and importo_aggiudicazione_raw is not null)
            or (ribasso_aggiudicazione is null and ribasso_aggiudicazione_raw is not null)
        ) as flag_aggiudicazione_non_leggibile
    from {{ ref('int_aggiudicazioni__corrente') }}
    group by cig
),

con_aggiudicatario as (
    select distinct cig from {{ ref('int_aggiudicatari__corrente') }}
),

stazioni as (
    select distinct codice_ausa
    from {{ ref('stg_anac__stazioni_appaltanti') }}
    where codice_ausa is not null
),

logaritmi as (
    select
        cig,
        coalesce(divisione_cpv, 'ND') as gruppo_cpv,
        coalesce(oggetto_principale_contratto, 'ND') as gruppo_oggetto,
        log10(importo_lotto) as log_importo
    from lotti
    where importo_lotto > 0
),

mediane as (
    select
        gruppo_cpv,
        gruppo_oggetto,
        count(*) as n_gruppo,
        median(log_importo) as mediana
    from logaritmi
    group by gruppo_cpv, gruppo_oggetto
),

deviazioni as (
    select
        l.cig,
        l.gruppo_cpv,
        l.gruppo_oggetto,
        abs(l.log_importo - m.mediana) as deviazione,
        m.n_gruppo
    from logaritmi as l
    inner join mediane as m
        on l.gruppo_cpv = m.gruppo_cpv and l.gruppo_oggetto = m.gruppo_oggetto
),

mad as (
    select gruppo_cpv, gruppo_oggetto, median(deviazione) as mad
    from deviazioni
    group by gruppo_cpv, gruppo_oggetto
),

robusto as (
    select
        d.cig,
        coalesce(
            d.n_gruppo >= 30
            and m.mad > 0
            and d.deviazione > {{ var('mad_fattore') }} * 1.4826 * m.mad,
            false
        ) as flag_importo_mad
    from deviazioni as d
    inner join mad as m
        on d.gruppo_cpv = m.gruppo_cpv and d.gruppo_oggetto = m.gruppo_oggetto
),

flag as (
    select
        l.cig,
        l.divisione_cpv,
        l.n_versioni,
        coalesce(s.flag_duplicato_esatto, false) as flag_duplicato_esatto,
        coalesce(s.flag_duplicato_conflittuale, false) as flag_duplicato_conflittuale,
        coalesce(l.data_scadenza_offerta < l.data_pubblicazione, false)
        or coalesce(a.data_aggiudicazione < l.data_pubblicazione, false)
        or coalesce(
            least(l.data_pubblicazione, l.data_scadenza_offerta, a.data_aggiudicazione) < date '2007-01-01', false
        )
        or coalesce(
            greatest(l.data_pubblicazione, l.data_scadenza_offerta, a.data_aggiudicazione)
            > {{ data_riferimento() }} + interval 2 year,
            false
        ) as flag_data_impossibile,
        coalesce(l.importo_lotto <= 0, false) as flag_importo_non_positivo,
        coalesce(
            l.importo_complessivo_gara > 0 and l.importo_lotto > l.importo_complessivo_gara + 0.01, false
        ) as flag_importo_oltre_gara,
        coalesce(l.importo_lotto > {{ var('importo_max_plausibile') }}, false) as flag_importo_implausibile,
        coalesce(
            (l.importo_lotto is null and l.importo_lotto_raw is not null)
            or (l.importo_complessivo_gara is null and l.importo_complessivo_gara_raw is not null),
            false
        ) as flag_importo_non_leggibile,
        coalesce(r.flag_importo_mad, false) as flag_importo_mad,
        coalesce((l.esito = 'AGGIUDICATA' or a.cig is not null) and g.cig is null, false)
            as flag_senza_aggiudicatario,
        coalesce(l.codice_ausa is not null and st.codice_ausa is null, false) as flag_stazione_orfana,
        coalesce(a.flag_ribasso_fuori_range, false) as flag_ribasso_fuori_range,
        coalesce(a.flag_aggiudicazione_non_leggibile, false) as flag_aggiudicazione_non_leggibile
    from lotti as l
    left join storia as s on l.cig = s.cig
    left join aggiudicazioni as a on l.cig = a.cig
    left join con_aggiudicatario as g on l.cig = g.cig
    left join stazioni as st on l.codice_ausa = st.codice_ausa
    left join robusto as r on l.cig = r.cig
)

select
    *,
    flag_importo_non_positivo
    or flag_importo_oltre_gara
    or flag_importo_implausibile
    or flag_importo_non_leggibile
    or flag_importo_mad as flag_importo_anomalo
from flag

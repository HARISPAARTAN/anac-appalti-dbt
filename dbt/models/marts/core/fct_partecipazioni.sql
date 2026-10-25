-- Ponte CIG × operatore × ruolo. Le persone fisiche compaiono solo come PERSONA_FISICA, senza identità:
-- più persone fisiche dello stesso lotto e ruolo condividono la riga e si contano con n_righe_*
-- (ogni persona è una riga distinta perché l'impronta di riga contiene l'ordinale, mai confrontato tra file).
with lotti as (
    select cig from {{ ref('fct_lotti') }}
),

righe as (
    select
        cig,
        coalesce(ruolo, 'ND') as ruolo,
        {{ chiave_operatore('tipo_soggetto_privacy', 'codice_fiscale') }} as operatore_key,
        'partecipanti' as fonte
    from {{ ref('int_partecipanti__corrente') }}
    union all
    select
        cig,
        coalesce(ruolo, 'ND') as ruolo,
        {{ chiave_operatore('tipo_soggetto_privacy', 'codice_fiscale') }} as operatore_key,
        'aggiudicatari' as fonte
    from {{ ref('int_aggiudicatari__corrente') }}
),

aggregate as (
    select
        r.cig,
        r.operatore_key,
        r.ruolo,
        bool_or(r.fonte = 'aggiudicatari') as flag_aggiudicatario,
        bool_or(r.fonte = 'partecipanti') as flag_partecipante,
        count(*) filter (where r.fonte = 'partecipanti') as n_righe_partecipanti,
        count(*) filter (where r.fonte = 'aggiudicatari') as n_righe_aggiudicatari
    from righe as r
    inner join lotti as l on r.cig = l.cig
    group by r.cig, r.operatore_key, r.ruolo
)

select
    {{ dbt_utils.generate_surrogate_key(['cig', 'operatore_key', 'ruolo']) }} as partecipazione_key,
    *
from aggregate

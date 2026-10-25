-- Aggiudicatari correnti: righe del file più recente per (cig, id_aggiudicazione), senza duplicati esatti.
with correnti as (
    {{ righe_correnti(ref('stg_anac__aggiudicatari'), ['cig', 'id_aggiudicazione']) }}
)

select
    {{ dbt_utils.generate_surrogate_key(['cig', '_risorsa', '_hash_riga']) }} as aggiudicatario_key,
    *
from correnti
where cig is not null

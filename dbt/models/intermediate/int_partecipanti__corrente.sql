-- Partecipanti correnti: righe del file più recente per CIG, senza duplicati esatti.
with correnti as (
    {{ righe_correnti(ref('stg_anac__partecipanti'), ['cig']) }}
)

select
    {{ dbt_utils.generate_surrogate_key(['cig', '_risorsa', '_hash_riga']) }} as partecipante_key,
    *
from correnti
where cig is not null

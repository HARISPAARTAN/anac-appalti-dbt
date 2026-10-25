{#- Righe correnti di una tabella figlia (aggiudicatari, partecipanti): per ogni valore delle chiavi
    si tengono solo le righe del file più recente (_data_snapshot, poi _risorsa) e si tolgono i
    duplicati esatti (stesso _hash_riga nello stesso file). -#}
{% macro righe_correnti(relazione, chiavi) -%}
with marcate as (
    select
        *,
        dense_rank() over (
            partition by {{ chiavi | join(', ') }}
            order by _data_snapshot desc, _risorsa desc
        ) as _rango_file,
        row_number() over (
            partition by {{ chiavi | join(', ') }}, _risorsa, _hash_riga
            order by _caricato_il
        ) as _copia
    from {{ relazione }}
)
select * exclude (_rango_file, _copia)
from marcate
where _rango_file = 1 and _copia = 1
{%- endmacro %}

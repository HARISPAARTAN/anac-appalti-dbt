{#- Avviso: righe con un testo non vuoto che la tipizzazione di staging trasforma in NULL (data o intero illeggibile).
    Una perdita qui toglie il lotto dai mart a base temporale o dalla logica dell'offerta unica senza altri segnali.
    Si applica alle colonne delle sources (generate da `appalti contratti sync`). -#}
{% test perdita_parsing(model, column_name, tipo) %}
{{ config(severity='warn') }}

select
    {{ column_name }} as valore_grezzo,
    _risorsa
from {{ model }}
where {{ condizione_perdita_parsing(column_name, tipo) }}
{% endtest %}

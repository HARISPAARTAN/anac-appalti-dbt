-- Errore: un codice fiscale personale (16 caratteri) compare in un mart o in una chiave operatore.
-- Solo modelli foglia: un fallimento non salta altri modelli.
{% set colonne = [
    ('dim_operatori', 'operatore_key'),
    ('dim_operatori', 'codice_fiscale'),
    ('dim_operatori', 'denominazione'),
    ('fct_partecipazioni', 'operatore_key'),
    ('fct_subappalti', 'operatore_key'),
    ('fct_subappalti', 'subappaltante_key'),
    ('mart_stazioni_appaltanti', 'codice_ausa'),
    ('mart_stazioni_appaltanti', 'denominazione'),
] %}
{% for modello, colonna in colonne %}
select '{{ modello }}' as modello, '{{ colonna }}' as colonna, cast({{ colonna }} as varchar) as valore
from {{ ref(modello) }}
where regexp_matches(
    upper(cast({{ colonna }} as varchar)),
    '(^|[^A-Z0-9])[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]([^A-Z0-9]|$)'
)
{% if not loop.last %}union all{% endif %}
{% endfor %}

-- Perdite di tipizzazione sulle date e sui conteggi che alimentano i mart: righe delle sources con un testo non
-- vuoto e valore tipizzato NULL. Tutte le righe atterrate (anche le versioni superate). Stesso elenco di
-- CONTROLLI_PARSING in src/anac_appalti/contratti.py (verificato da un test Python), stessa condizione del test
-- generico perdita_parsing sulle sources.
{% set controlli = [
    ('cig', 'data_pubblicazione', 'data'),
    ('cig', 'data_scadenza_offerta', 'data'),
    ('aggiudicazioni', 'data_aggiudicazione_definitiva', 'data'),
    ('aggiudicazioni', 'numero_offerte_ammesse', 'intero'),
    ('aggiudicazioni', 'num_imprese_offerenti', 'intero'),
    ('varianti', 'data_approvazione_variante', 'data'),
    ('subappalti', 'data_autorizzazione', 'data'),
] %}
{% for tabella, colonna, tipo in controlli %}
select
    '{{ tabella }}' as tabella,
    '{{ colonna }}' as colonna,
    cast(count(*) filter (where nullif(trim({{ colonna }}), '') is not null) as bigint) as n_valorizzate,
    cast(count(*) filter (where {{ condizione_perdita_parsing(colonna, tipo) }}) as bigint) as n_perdite
from {{ source('anac', tabella) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}

-- Errore: una colonna di staging, intermediate, core o radar ha un nome da dato personale.
-- depends_on: {{ ref('mart_appalti_regione_mese') }}
-- depends_on: {{ ref('mart_appalti_settore_cpv') }}
-- depends_on: {{ ref('mart_procedure') }}
-- depends_on: {{ ref('mart_tasso_aggiudicazione') }}
-- depends_on: {{ ref('mart_tempi_aggiudicazione') }}
-- depends_on: {{ ref('mart_concorrenza') }}
-- depends_on: {{ ref('mart_ribassi') }}
-- depends_on: {{ ref('mart_varianti_subappalti') }}
-- depends_on: {{ ref('mart_stazioni_appaltanti') }}
-- depends_on: {{ ref('dim_operatori') }}
-- depends_on: {{ ref('dim_data') }}
-- depends_on: {{ ref('fct_partecipazioni') }}
-- depends_on: {{ ref('int_riconciliazione') }}
-- depends_on: {{ ref('int_perdite_parsing') }}
select table_schema, table_name, column_name
from information_schema.columns
where table_schema in ('staging', 'intermediate', 'core', 'radar')
    and regexp_matches(lower(column_name), '(^|_)(rup|nome|cognome|responsabile)(_|$)')

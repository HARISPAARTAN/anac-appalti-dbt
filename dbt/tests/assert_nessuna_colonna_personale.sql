-- Errore: una colonna di staging, intermediate, core o radar ha un nome da dato personale.
-- depends_on: {{ ref('int_lotti__qualita') }}
-- depends_on: {{ ref('int_operatori') }}
-- depends_on: {{ ref('int_riconciliazione') }}
select table_schema, table_name, column_name
from information_schema.columns
where table_schema in ('staging', 'intermediate', 'core', 'radar')
    and regexp_matches(lower(column_name), '(^|_)(rup|nome|cognome|responsabile)(_|$)')

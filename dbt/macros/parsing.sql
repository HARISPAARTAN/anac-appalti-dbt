{#- Tipizzazione dei campi ANAC, letti come testo (all_varchar) in landing. -#}

{% macro testo(colonna) -%}
nullif(trim({{ colonna }}), '')
{%- endmacro %}

{% macro codice(colonna) -%}
upper(nullif(trim({{ colonna }}), ''))
{%- endmacro %}

{#- Codici numerici a volte scritti come "27.0": si toglie la parte decimale nulla. -#}
{% macro codice_numerico(colonna) -%}
regexp_replace(upper(nullif(trim({{ colonna }}), '')), '\.0+$', '')
{%- endmacro %}

{#- Date ISO (anche con ora: si tengono i primi 10 caratteri) oppure gg/mm/aaaa. -#}
{% macro parse_data_it(colonna) -%}
coalesce(
    try_cast(left(nullif(trim({{ colonna }}), ''), 10) as date),
    cast(try_strptime(nullif(trim({{ colonna }}), ''), '%d/%m/%Y') as date)
)
{%- endmacro %}

{% macro parse_importo(colonna) -%}
try_cast(try_cast(replace(nullif(trim({{ colonna }}), ''), ',', '.') as double) as decimal(18, 2))
{%- endmacro %}

{% macro parse_intero(colonna) -%}
coalesce(
    try_cast(nullif(trim({{ colonna }}), '') as bigint),
    try_cast(try_cast(nullif(trim({{ colonna }}), '') as double) as bigint)
)
{%- endmacro %}

{% macro parse_flag(colonna) -%}
case
    when upper(trim({{ colonna }})) in ('1', '1.0', 'TRUE', 'T', 'S', 'SI', 'Y', 'YES') then true
    when upper(trim({{ colonna }})) in ('0', '0.0', 'FALSE', 'F', 'N', 'NO') then false
end
{%- endmacro %}

{% macro data_riferimento() -%}
{%- set valore = var('data_riferimento', none) -%}
{%- if valore -%}
date '{{ valore }}'
{%- else -%}
current_date
{%- endif -%}
{%- endmacro %}

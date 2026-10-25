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

{#- Date ISO (anche con ora: si tengono i primi 10 caratteri) oppure gg/mm/aaaa (anche con ora). Il resto è NULL. -#}
{% macro parse_data_it(colonna) -%}
coalesce(
    try_cast(left(nullif(trim({{ colonna }}), ''), 10) as date),
    cast(
        try_strptime(regexp_extract(trim({{ colonna }}), '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'), '%d/%m/%Y') as date
    )
)
{%- endmacro %}

{#- Numero decimale in testo normalizzato al formato con il punto decimale e senza separatori delle migliaia.
    Riconosce: 1234.56 (formato ANAC), 1234,56, 1.234,56 (italiano), 1,234.56 (inglese), 1.234.567 e 1,234,567
    (migliaia senza decimali). Un solo punto è sempre il separatore decimale (il formato ANAC è verificato:
    12.345 è dodici virgola trecentoquarantacinque, non dodicimilatrecentoquarantacinque). Una sola virgola
    seguita da tre cifre (1,234) è ambigua tra migliaia e decimali: con `virgola_ambigua` vero (importi) resta
    NULL, con falso (ribasso, che non ha migliaia) è decimale. Tutto ciò che non è un numero resta NULL: il
    chiamante conserva il testo originale in una colonna _raw e la qualità dei dati segnala la perdita
    (int_lotti__qualita). -#}
{% macro numero_normalizzato(colonna, virgola_ambigua=true) -%}
case
    {% if virgola_ambigua -%}
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]{1,3},[0-9]{3}') then null
    {% endif -%}
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]{1,3}(\.[0-9]{3})+,[0-9]+')
        then replace(replace(trim({{ colonna }}), '.', ''), ',', '.')
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]{1,3}(,[0-9]{3})+\.[0-9]+')
        then replace(trim({{ colonna }}), ',', '')
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]{1,3}(\.[0-9]{3}){2,}')
        then replace(trim({{ colonna }}), '.', '')
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]{1,3}(,[0-9]{3}){2,}')
        then replace(trim({{ colonna }}), ',', '')
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]+,[0-9]+') then replace(trim({{ colonna }}), ',', '.')
    when regexp_full_match(trim({{ colonna }}), '-?[0-9]+(\.[0-9]+)?') then trim({{ colonna }})
end
{%- endmacro %}

{#- Importo in euro, decimal(18,2). Fuori formato o con 16 cifre intere o più (oltre decimal(18,2)): NULL. -#}
{% macro parse_importo(colonna) -%}
try_cast({{ numero_normalizzato(colonna) }} as decimal(18, 2))
{%- endmacro %}

{% macro parse_ribasso(colonna) -%}
try_cast({{ numero_normalizzato(colonna, virgola_ambigua=false) }} as double)
{%- endmacro %}

{#- Interi: "27" e "27.0" sì, "27.5" no (NULL, non arrotondato: il cast di DuckDB da testo arrotonderebbe). -#}
{% macro parse_intero(colonna) -%}
coalesce(
    try_cast(case when regexp_full_match(trim({{ colonna }}), '-?[0-9]+') then trim({{ colonna }}) end as bigint),
    case
        when try_cast(nullif(trim({{ colonna }}), '') as double) = floor(try_cast(nullif(trim({{ colonna }}), '') as double))
            then try_cast(try_cast(nullif(trim({{ colonna }}), '') as double) as bigint)
    end
)
{%- endmacro %}

{% macro parse_flag(colonna) -%}
case
    when upper(trim({{ colonna }})) in ('1', '1.0', 'TRUE', 'T', 'S', 'SI', 'Y', 'YES') then true
    when upper(trim({{ colonna }})) in ('0', '0.0', 'FALSE', 'F', 'N', 'NO') then false
end
{%- endmacro %}

{#- Condizione di perdita: testo non vuoto che la macro di tipizzazione (`data` = parse_data_it, `intero` =
    parse_intero) trasforma in NULL. Usata dal test generico perdita_parsing e da int_perdite_parsing. -#}
{% macro condizione_perdita_parsing(colonna, tipo) -%}
nullif(trim({{ colonna }}), '') is not null
and {% if tipo == 'data' -%}
{{ parse_data_it(colonna) }}
{%- elif tipo == 'intero' -%}
{{ parse_intero(colonna) }}
{%- else -%}
{{ exceptions.raise_compiler_error("condizione_perdita_parsing: tipo sconosciuto " ~ tipo) }}
{%- endif %} is null
{%- endmacro %}

{% macro data_riferimento() -%}
{%- set valore = var('data_riferimento', none) -%}
{%- if valore -%}
date '{{ valore }}'
{%- else -%}
current_date
{%- endif -%}
{%- endmacro %}

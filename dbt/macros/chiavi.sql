{#- Chiave intera aaaammgg verso dim_data (NULL se la data manca). -#}
{% macro chiave_data(colonna) -%}
cast(strftime({{ colonna }}, '%Y%m%d') as integer)
{%- endmacro %}

{#- Chiave operatore: il codice per le persone giuridiche, un membro anonimo per tutti gli altri. -#}
{% macro chiave_operatore(tipo_privacy, codice) -%}
case
    when {{ tipo_privacy }} = 'persona_giuridica' then {{ codice }}
    when {{ tipo_privacy }} = 'persona_fisica' then 'PERSONA_FISICA'
    else 'NON_VERIFICABILE'
end
{%- endmacro %}

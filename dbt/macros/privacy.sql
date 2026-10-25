{#- Gemello SQL di anac_appalti.privacy.classifica_codice_fiscale: stessi modelli,
    verificato da tests/unit/test_privacy_sql.py. -#}
{% macro classifica_cf(colonna) -%}
case
    when nullif(trim({{ colonna }}), '') is null then 'assente'
    when regexp_full_match(upper(trim({{ colonna }})), '[0-9]{11}') then 'persona_giuridica'
    when regexp_full_match(upper(trim({{ colonna }})), '[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]') then 'persona_fisica'
    else 'non_verificabile'
end
{%- endmacro %}

{#- Classe da riportare in staging. Il landing annulla già i codici delle persone fisiche e ne conserva la
    classe in `_classe_*`: se il codice è ancora presente lo si riclassifica (seconda linea di difesa), altrimenti
    si usa la classe del landing. L'identità non viene mai ricostruita: serve solo a contare e a spiegare i NULL. -#}
{% macro classe_privacy(colonna, classe_landing) -%}
case
    when {{ classifica_cf(colonna) }} <> 'assente' then {{ classifica_cf(colonna) }}
    else coalesce(nullif(trim({{ classe_landing }}), ''), 'assente')
end
{%- endmacro %}

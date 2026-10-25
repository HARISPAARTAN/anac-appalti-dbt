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

{#- Classe da riportare in staging. `classe_presente` è la classifica_cf del codice ancora presente (calcolata una
    sola volta per colonna dal modello). Il landing annulla già i codici delle persone fisiche e ne conserva la
    classe in `_classe_*`: se il codice è ancora presente si usa la sua classe (seconda linea di difesa), altrimenti
    la classe del landing. L'identità non viene mai ricostruita: serve solo a contare e a spiegare i NULL. -#}
{% macro classe_privacy(classe_presente, classe_landing) -%}
case
    when {{ classe_presente }} <> 'assente' then {{ classe_presente }}
    else coalesce(nullif(trim({{ classe_landing }}), ''), 'assente')
end
{%- endmacro %}

{#- Vero se il testo contiene un codice fiscale di persona fisica (gemello di privacy.RE_CF_IN_TESTO). Nei dati reali
    alcune ditte individuali riportano come denominazione il codice fiscale del titolare: quella denominazione va
    annullata anche se il codice fiscale della riga è una partita IVA di 11 cifre. -#}
{% macro contiene_cf_persona(colonna) -%}
coalesce(regexp_matches(upper({{ colonna }}), '(^|[^A-Z0-9])[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]([^A-Z0-9]|$)'), false)
{%- endmacro %}

{#- Forme giuridiche che dicono "individuo" (anagrafe delle stazioni appaltanti e tipo_soggetto degli operatori). Una
    sola lista per i due usi; gemella di privacy.NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI. "IMPRESA SINGOLA
    (IMPRENDITORI INDIVIDUALI, ... SOCIETA' COMMERCIALI ...)" non è in lista: mescola persone e società. -#}
{% macro forme_giuridiche_individuali() -%}
(
    'ALTRI LAVORATORI AUTONOMI',
    'DITTA INDIVIDUALE',
    'DITTE INDIVIDUALI',
    'IMPRESE INDIVIDUALI ARTIGIANE',
    'IMPRESE INDIVIDUALI COMMERCIALI',
    'LAVORATORI AUTONOMI - PROFESSIONISTI',
    'LIBERO PROFESSIONISTA'
)
{%- endmacro %}

{#- Vero se la stazione appaltante è una persona fisica: codice fiscale personale (16 caratteri) oppure forma giuridica
    individuale dell'anagrafe (ditta individuale, libero professionista, lavoratore autonomo). Gemello di
    privacy.e_stazione_persona_fisica, verificato da tests/unit/test_privacy_sql.py. Le tre colonne sono già
    normalizzate dallo staging (maiuscole, senza spazi ai bordi). -#}
{% macro stazione_persona_fisica(codice_fiscale, natura_codice, natura_descrizione) -%}
(
    coalesce(regexp_full_match({{ codice_fiscale }}, '[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]'), false)
    or coalesce({{ natura_codice }} in ('56', '58', '59', '60', '61', 'A070'), false)
    or coalesce(upper({{ natura_descrizione }}) in {{ forme_giuridiche_individuali() }}, false)
)
{%- endmacro %}

{#- Vero se il tipo_soggetto dell'operatore è una forma giuridica individuale (ditta individuale, libero professionista...):
    il suo nome e la sua partita IVA sono dati personali, quindi la denominazione è annullata anche se il codice è di
    11 cifre. Il codice resta come chiave locale. Gemello di privacy.e_tipo_soggetto_individuale. -#}
{% macro tipo_soggetto_individuale(colonna) -%}
coalesce(upper(trim({{ colonna }})) in {{ forme_giuridiche_individuali() }}, false)
{%- endmacro %}

{#- Codici AUSA delle stazioni che l'anagrafe dichiara persone fisiche (codice fiscale di 16 caratteri o forma giuridica
    individuale), letti dalla sorgente, più la classificazione manuale del seed ausa_persone_fisiche. Servono a togliere il nome anche dalle righe dei lotti (stg_anac__cig) e al test
    che confronta le chiavi dei mart con l'anagrafe (assert_nessuna_stazione_personale_nei_mart). -#}
{% macro ausa_stazioni_personali() -%}
select distinct upper(trim(codice_ausa)) as codice_ausa
from {{ source('anac', 'stazioni_appaltanti') }}
where upper(trim(codice_ausa)) is not null
    and {{ stazione_persona_fisica(
        "upper(trim(codice_fiscale))",
        "regexp_replace(upper(trim(natura_giuridica_codice)), '\\.0+$', '')",
        "trim(natura_giuridica_descrizione)"
    ) }}
union
select upper(trim(codice_ausa)) as codice_ausa
from {{ ref('ausa_persone_fisiche') }}
{%- endmacro %}

{#- Parole che segnalano un ente o una società (non una persona) in una denominazione. Gemella di
    scansione_privacy.MARCATORI_ENTE (stesso elenco, confrontato da tests/unit/test_scansione_privacy.py). Usata dal
    modello int_stazioni_da_verificare. -#}
{% macro parole_ente() -%}
['AGENZIA', 'ALER', 'AMBITO', 'ASL', 'ASSOCIAZIONE', 'ASST', 'AUSL', 'AUTORITA', 'AZIENDA', 'AZIONE', 'BIBLIOTECA', 'CAMERA', 'CITTA', 'COLLEGIO', 'COMANDO', 'COMPRENSIVO', 'COMPRENSORIO', 'COMUNALE', 'COMUNE', 'COMUNI', 'COMUNITA', 'CONSORZIO', 'COOP', 'COOPERATIVA', 'CUC', 'DIOCESI', 'DIPARTIMENTO', 'DIREZIONE', 'ENTE', 'ENTI', 'FONDAZIONE', 'GRUPPO', 'ISTITUTO', 'ISTITUZIONE', 'ITALIANA', 'ITALIANO', 'LAVORI', 'LICEO', 'LOCALE', 'METROPOLITANA', 'MINISTERO', 'MUSEO', 'NAZIONALE', 'ORDINE', 'OSPEDALE', 'PARCO', 'PARROCCHIA', 'POLICLINICO', 'PREFETTURA', 'PROVINCIA', 'PROVINCIALE', 'QUESTURA', 'REGIONALE', 'REGIONE', 'SAS', 'SCARL', 'SCIENTIFICO', 'SCUOLA', 'SERVIZI', 'SERVIZIO', 'SNC', 'SOC', 'SOCIETA', 'SPA', 'SRL', 'STATALE', 'TEATRO', 'TERRA', 'TERRITORIALE', 'TRIBUNALE', 'UNIONE', 'UNIVERSITA']
{%- endmacro %}

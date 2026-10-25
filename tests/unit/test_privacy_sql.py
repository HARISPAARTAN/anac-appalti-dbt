import duckdb
import jinja2

from anac_appalti.config import carica_impostazioni
from anac_appalti.privacy import (
    MODELLO_CF_PERSONA,
    MODELLO_PIVA,
    NATURE_GIURIDICHE_INDIVIDUALI_CODICI,
    NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI,
    cerca_cf_personali,
    classifica_codice_fiscale,
    e_stazione_persona_fisica,
    e_tipo_soggetto_individuale,
)

MACRO = (carica_impostazioni().dbt_dir / "macros" / "privacy.sql").read_text(encoding="utf-8")
CODICI = [
    "01199250158",
    " 01199250158 ",
    "RSSMRA80A01H501U",
    "rssmra80a01h501u",
    "RSSMRA80A01H50QU",
    "STTLII66TAZ129T",
    "DE123456789",
    "0119925015",
    "",
    None,
]


def test_stessi_modelli_del_python():
    assert f"'{MODELLO_PIVA}'" in MACRO
    assert f"'{MODELLO_CF_PERSONA}'" in MACRO


def test_macro_classifica_come_il_python():
    espressione = jinja2.Environment().from_string(MACRO + "{{ classifica_cf('codice') }}").render()
    con = duckdb.connect()
    con.execute("create table t (n integer, codice varchar)")
    con.executemany("insert into t values (?, ?)", list(enumerate(CODICI)))
    risultati = dict(con.execute(f"select n, {espressione} from t").fetchall())
    con.close()
    for n, codice in enumerate(CODICI):
        assert risultati[n] == classifica_codice_fiscale(codice), repr(codice)


LANDING = [None, "", "persona_fisica", "non_verificabile"]


def test_classe_privacy_usa_il_codice_presente_poi_il_landing():
    # la classe del codice presente si calcola una volta sola e si passa già espansa
    sql = "{{ classe_privacy(classifica_cf('codice'), 'classe') }}"
    espressione = jinja2.Environment().from_string(MACRO + sql).render()
    con = duckdb.connect()
    con.execute("create table t (n integer, codice varchar, classe varchar)")
    righe = [
        (n, codice, classe) for n, (codice, classe) in enumerate((c, k) for c in CODICI for k in LANDING)
    ]
    con.executemany("insert into t values (?, ?, ?)", righe)
    risultati = dict(con.execute(f"select n, {espressione} from t").fetchall())
    con.close()
    for n, codice, classe in righe:
        presente = classifica_codice_fiscale(codice)
        atteso = presente if presente != "assente" else (classe or "assente")
        assert risultati[n] == atteso, (codice, classe)


def test_macro_contiene_cf_persona_come_il_python():
    testi = [
        None,
        "",
        "IMPRESA ESEMPIO S.R.L.",
        "RSSMRA80A01H501U",
        "ditta rssmra80a01h501u di esempio",
        "XRSSMRA80A01H501UX",
        "10000104729",
    ]
    espressione = jinja2.Environment().from_string(MACRO + "{{ contiene_cf_persona('t') }}").render()
    con = duckdb.connect()
    con.execute("create table x (n integer, t varchar)")
    con.executemany("insert into x values (?, ?)", list(enumerate(testi)))
    risultati = dict(con.execute(f"select n, {espressione} from x").fetchall())
    con.close()
    for n, testo in enumerate(testi):
        assert risultati[n] == bool(cerca_cf_personali(testo or "")), repr(testo)


STAZIONI = [
    # (codice fiscale, codice natura giuridica, descrizione natura giuridica)
    ("80000000001", "1", "AMMINISTRAZIONI COMUNALI"),
    ("RSSMRA80A01H501U", "1", "AMMINISTRAZIONI COMUNALI"),  # codice fiscale personale
    ("12345678901", "60", "DITTE INDIVIDUALI"),  # individuale con partita IVA
    ("12345678901", "A070", None),  # solo il codice
    ("12345678901", None, "LIBERO PROFESSIONISTA"),  # solo la descrizione
    ("12345678901", "59", "IMPRESE INDIVIDUALI COMMERCIALI"),
    ("12345678901", "58", "IMPRESE INDIVIDUALI ARTIGIANE"),
    ("12345678901", "61", "LAVORATORI AUTONOMI - PROFESSIONISTI"),
    ("12345678901", "56", "ALTRI LAVORATORI AUTONOMI"),
    ("12345678901", "27", "ASSOCIAZIONI TRA PROFESSIONISTI"),  # un'associazione non è un individuo
    ("12345678901", "SC", None),
    (None, None, None),
    ("", "", ""),
    ("STTLII66TAZ129T", None, None),  # non verificabile, non personale
]


def test_stazione_persona_fisica_come_il_python():
    espressione = (
        jinja2.Environment()
        .from_string(
            MACRO
            + "{{ stazione_persona_fisica('upper(trim(cf))', 'upper(trim(cod))', 'upper(trim(descr))') }}"
        )
        .render()
    )
    con = duckdb.connect()
    con.execute("create table s (n integer, cf varchar, cod varchar, descr varchar)")
    con.executemany("insert into s values (?, ?, ?, ?)", [(n, *riga) for n, riga in enumerate(STAZIONI)])
    risultati = dict(con.execute(f"select n, {espressione} from s").fetchall())
    con.close()
    for n, (cf, codice, descrizione) in enumerate(STAZIONI):
        assert risultati[n] == e_stazione_persona_fisica(cf, codice, descrizione), (cf, codice, descrizione)
    assert sum(risultati.values()) == 8


def test_stesse_forme_giuridiche_del_python():
    for codice in NATURE_GIURIDICHE_INDIVIDUALI_CODICI:
        assert f"'{codice}'" in MACRO
    for descrizione in NATURE_GIURIDICHE_INDIVIDUALI_DESCRIZIONI:
        assert f"'{descrizione}'" in MACRO


TIPI_SOGGETTO = [
    "DITTA INDIVIDUALE",
    " ditte individuali ",
    "IMPRESE INDIVIDUALI ARTIGIANE",
    "LIBERO PROFESSIONISTA",
    "IMPRESA",
    "IMPRESA SINGOLA (IMPRENDITORI INDIVIDUALI, ANCHE ARTIGIANI, SOCIETA' COMMERCIALI, SOCIETA' COOPERATIVE)",
    "ASSOCIAZIONI TRA PROFESSIONISTI",
    "",
    None,
]


def test_tipo_soggetto_individuale_come_il_python():
    espressione = jinja2.Environment().from_string(MACRO + "{{ tipo_soggetto_individuale('t') }}").render()
    con = duckdb.connect()
    con.execute("create table x (n integer, t varchar)")
    con.executemany("insert into x values (?, ?)", list(enumerate(TIPI_SOGGETTO)))
    risultati = dict(con.execute(f"select n, {espressione} from x").fetchall())
    con.close()
    for n, tipo in enumerate(TIPI_SOGGETTO):
        assert risultati[n] == e_tipo_soggetto_individuale(tipo), repr(tipo)
    assert sum(risultati.values()) == 4

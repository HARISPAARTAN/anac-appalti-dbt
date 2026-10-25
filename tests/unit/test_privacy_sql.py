import duckdb
import jinja2

from anac_appalti.config import carica_impostazioni
from anac_appalti.privacy import MODELLO_CF_PERSONA, MODELLO_PIVA, classifica_codice_fiscale

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

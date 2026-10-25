"""Comportamento del lettore CSV con `escape = '\\'` (OPZIONI_CSV) e del conteggio fisico dei record.

I test del lettore documentano che cosa fa DuckDB con questi input, non che sia desiderabile: un backslash isolato
viene eliminato in silenzio e uno prima della virgoletta di chiusura fa assorbire le righe seguenti (oppure fa
fallire la lettura). Nei 73 file reali del 2026-10-25 non ce n'è nessuno: ANAC raddoppia i backslash letterali.
Se una nuova versione di DuckDB cambia questi risultati, il test lo segnala.
"""

from pathlib import Path

import duckdb
import pytest

from anac_appalti.landing import OPZIONI_CSV, conta_record_csv

BS = "\\"
TESTATA = '"a";"b";"c"\n'


def leggi(tmp_path: Path, testo: str) -> list[tuple]:
    sorgente = tmp_path / "prova.csv"
    sorgente.write_bytes(testo.encode("utf-8"))
    con = duckdb.connect()
    try:
        return con.execute(f"select * from read_csv('{sorgente.as_posix()}', {OPZIONI_CSV})").fetchall()
    finally:
        con.close()


def test_virgolette_con_backslash_diventano_virgolette_nel_valore(tmp_path: Path):
    testo = TESTATA + f'"1";"A {BS}"B{BS}" C";"x"\n"2";"y";"z"\n'
    assert leggi(tmp_path, testo) == [("1", 'A "B" C', "x"), ("2", "y", "z")]


def test_backslash_raddoppiato_diventa_un_solo_backslash(tmp_path: Path):
    testo = TESTATA + f'"1";"A{BS}{BS}B";"x"\n'
    assert leggi(tmp_path, testo) == [("1", f"A{BS}B", "x")]


def test_backslash_raddoppiato_prima_della_virgoletta_di_chiusura_chiude_il_campo(tmp_path: Path):
    """È così che ANAC scrive un valore che finisce con un backslash: le righe seguenti restano separate."""
    testo = TESTATA + f'"1";"C:{BS}{BS}";"x"\n"2";"y";"z"\n'
    assert leggi(tmp_path, testo) == [("1", f"C:{BS}", "x"), ("2", "y", "z")]


def test_backslash_isolato_viene_eliminato_in_silenzio(tmp_path: Path):
    testo = TESTATA + f'"1";"A{BS}B";"x"\n'
    assert leggi(tmp_path, testo) == [("1", "AB", "x")]


def test_backslash_isolato_prima_della_virgoletta_di_chiusura_fa_fallire_la_lettura(tmp_path: Path):
    """La virgoletta di chiusura diventa un escape: il campo non si chiude e DuckDB non riconosce il dialetto."""
    testo = TESTATA + f'"1";"C:{BS}";"z"\n"2";"x";"y"\n"3";"p";"q"\n"4";"r";"s"\n'
    with pytest.raises(duckdb.InvalidInputException):
        leggi(tmp_path, testo)


def test_backslash_isolato_in_ultimo_campo_assorbe_le_righe_seguenti(tmp_path: Path):
    """Caso silenzioso: tre righe finiscono in un solo valore. Il conteggio fisico dei record lo mostrerebbe."""
    testo = TESTATA + f'"1";"p";"C:{BS}"\n"2";"x";"y"\n"3";"p";"q"\n"4";"r";"s"'
    righe = leggi(tmp_path, testo)
    assert len(righe) == 1
    assert righe[0][0] == "1" and righe[0][2].startswith('C:"\n"2"')


def test_conta_record_csv_conta_i_record_e_non_gli_a_capo(tmp_path: Path):
    testo = (
        TESTATA
        + f'"1";"A {BS}"B{BS}" C";"x"\n'
        + '"2";"due\nrighe\ndentro";"y"\n'
        + f'"3";"C:{BS}{BS}";"z"\n'
        + '"4";"ultimo";"w"'  # senza a capo finale
    )
    sorgente = tmp_path / "prova.csv"
    sorgente.write_bytes(testo.encode("utf-8"))
    assert conta_record_csv(sorgente) == 4
    assert len(leggi(tmp_path, testo)) == 4


def test_conta_record_csv_attraversa_i_blocchi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("anac_appalti.landing._BLOCCO_CONTEGGIO", 7)
    righe = [f'"{i}";"a\nb {BS}"c{BS}"";"{BS}{BS}"' for i in range(50)]
    sorgente = tmp_path / "prova.csv"
    sorgente.write_bytes((TESTATA + "\n".join(righe) + "\n").encode("utf-8"))
    assert conta_record_csv(sorgente) == 50


def test_conta_record_csv_condivide_la_regola_di_escape_con_il_lettore(tmp_path: Path):
    """Con un backslash isolato prima della virgoletta di chiusura il campo resta aperto fino alla fine del file:
    il lettore ne ricava una riga, il conteggio nessun record chiuso. I due numeri differiscono e la
    riconciliazione fisica segnala `differenza_fisica`."""
    testo = TESTATA + f'"1";"p";"C:{BS}"\n"2";"x";"y"\n"3";"p";"q"\n"4";"r";"s"'
    sorgente = tmp_path / "prova.csv"
    sorgente.write_bytes(testo.encode("utf-8"))
    assert conta_record_csv(sorgente) == 0
    assert len(leggi(tmp_path, testo)) == 1

import pytest

from anac_appalti.privacy import cerca_cf_personali, classifica_codice_fiscale


@pytest.mark.parametrize(
    ("codice", "atteso"),
    [
        ("01199250158", "persona_giuridica"),
        (" 01199250158 ", "persona_giuridica"),
        ("RSSMRA80A01H501U", "persona_fisica"),
        ("rssmra80a01h501u", "persona_fisica"),
        ("RSSMRA80A01H50QU", "persona_fisica"),
        ("STTLII66TAZ129T", "non_verificabile"),
        ("DE123456789", "non_verificabile"),
        ("0119925015", "non_verificabile"),
        ("", "assente"),
        (None, "assente"),
    ],
)
def test_classifica_codice_fiscale(codice, atteso):
    assert classifica_codice_fiscale(codice) == atteso


def test_cerca_cf_personali_nel_testo():
    testo = '"FX00000001";"RSSMRA80A01H501U";"01199250158";"IMPRESA ESEMPIO 01 S.R.L."'
    assert cerca_cf_personali(testo) == ["RSSMRA80A01H501U"]
    assert cerca_cf_personali('"FX00000101";"10000104729"') == []

import pytest

from anac_appalti.copertura import ErroreCopertura, calcola_copertura


def modello(nome: str, livello: str, descrizione: str = "x", chiave=None) -> tuple[str, dict]:
    uid = f"model.anac_appalti.{nome}"
    return uid, {
        "resource_type": "model",
        "package_name": "anac_appalti",
        "name": nome,
        "fqn": ["anac_appalti", livello, nome],
        "description": descrizione,
        "config": {"meta": {"chiave": chiave} if chiave else {}},
    }


def prova(
    nome_test: str, modello_uid: str, colonna: str | None = None, config: dict | None = None, **kwargs
) -> tuple[str, dict]:
    return f"test.anac_appalti.{nome_test}_{modello_uid}_{colonna}", {
        "resource_type": "test",
        "package_name": "anac_appalti",
        "attached_node": modello_uid,
        "column_name": colonna,
        "config": {"severity": "ERROR", **(config or {})},
        "test_metadata": {"name": nome_test, "kwargs": kwargs},
    }


def test_copertura_completa_e_mancanze():
    nodi = dict(
        [
            modello("stg_a", "staging"),
            prova("not_null", "model.anac_appalti.stg_a", "_hash_riga"),
            modello("int_b", "intermediate", chiave="cig"),
            prova("unique", "model.anac_appalti.int_b", "cig"),
            prova("not_null", "model.anac_appalti.int_b", "cig"),
            modello("mart_c", "marts", chiave=["regione", "anno"]),
            prova(
                "unique_combination_of_columns",
                "model.anac_appalti.mart_c",
                None,
                combination_of_columns=["anno", "regione"],
            ),
            prova("not_null", "model.anac_appalti.mart_c", "regione"),
            prova("not_null", "model.anac_appalti.mart_c", "anno"),
        ]
    )
    esito = calcola_copertura({"nodes": nodi})
    assert (esito.modelli, esito.conformi, esito.mancanze, esito.quota) == (3, 3, [], 1.0)

    nodi.update(
        dict([modello("int_d", "intermediate", descrizione=""), modello("mart_e", "marts", chiave="k")])
    )
    esito = calcola_copertura({"nodes": nodi})
    assert esito.conformi == 3 and esito.modelli == 5
    assert esito.mancanze == [
        "int_d: descrizione mancante",
        "int_d: chiave non dichiarata in config.meta.chiave",
        "mart_e: manca il test unique sulla chiave k",
        "mart_e: manca il test not_null su k",
    ]


INT_B = "model.anac_appalti.int_b"


def mart_con(*test: tuple[str, dict]) -> dict:
    return dict([modello("int_b", "intermediate", chiave="cig"), *test])


def test_manifest_vuoto_o_progetto_sbagliato_e_un_errore():
    with pytest.raises(ErroreCopertura):
        calcola_copertura({"nodes": {}})
    with pytest.raises(ErroreCopertura):
        calcola_copertura({})
    nodi = mart_con(prova("unique", INT_B, "cig"), prova("not_null", INT_B, "cig"))
    assert calcola_copertura({"nodes": nodi}).quota == 1.0
    with pytest.raises(ErroreCopertura):
        calcola_copertura({"nodes": nodi}, progetto="altro_progetto")


@pytest.mark.parametrize(
    "config",
    [
        {"where": "1=0"},
        {"severity": "warn"},
        {"limit": 0},
        {"enabled": False},
    ],
)
def test_un_test_con_filtro_o_solo_avviso_non_conta(config):
    senza_valore = mart_con(prova("unique", INT_B, "cig", config), prova("not_null", INT_B, "cig"))
    esito = calcola_copertura({"nodes": senza_valore})
    assert esito.mancanze == ["int_b: manca il test unique sulla chiave cig"]
    assert (esito.modelli, esito.conformi, esito.quota) == (1, 0, 0.0)
    senza_non_nullo = mart_con(prova("unique", INT_B, "cig"), prova("not_null", INT_B, "cig", config))
    assert calcola_copertura({"nodes": senza_non_nullo}).mancanze == ["int_b: manca il test not_null su cig"]


def test_staging_con_solo_un_not_null_filtrato_non_e_coperto():
    nodi = dict(
        [
            modello("stg_a", "staging"),
            prova("not_null", "model.anac_appalti.stg_a", "x", {"where": "1=0"}),
            prova("not_null", "model.anac_appalti.stg_a", "y", {"severity": "warn"}),
        ]
    )
    assert calcola_copertura({"nodes": nodi}).mancanze == ["stg_a: nessun test not_null"]


def test_coppia_unica_filtrata_non_conta():
    nodi = dict(
        [
            modello("mart_c", "marts", chiave=["regione", "anno"]),
            prova(
                "unique_combination_of_columns",
                "model.anac_appalti.mart_c",
                None,
                {"where": "anno > 2000"},
                combination_of_columns=["anno", "regione"],
            ),
            prova("not_null", "model.anac_appalti.mart_c", "regione"),
            prova("not_null", "model.anac_appalti.mart_c", "anno"),
        ]
    )
    assert calcola_copertura({"nodes": nodi}).mancanze == [
        "mart_c: manca unique_combination_of_columns su regione, anno"
    ]

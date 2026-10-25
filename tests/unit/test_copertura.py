from anac_appalti.copertura import calcola_copertura


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


def prova(nome_test: str, modello_uid: str, colonna: str | None = None, **kwargs) -> tuple[str, dict]:
    return f"test.anac_appalti.{nome_test}_{modello_uid}_{colonna}", {
        "resource_type": "test",
        "package_name": "anac_appalti",
        "attached_node": modello_uid,
        "column_name": colonna,
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

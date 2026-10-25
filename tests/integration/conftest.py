import pytest

from tests.integration.aiuti import esegui_mese


@pytest.fixture(scope="session")
def magazzino_mese1(tmp_path_factory):
    return esegui_mese(tmp_path_factory.mktemp("mese1"), 1)


@pytest.fixture(scope="session")
def magazzino_mese2(tmp_path_factory):
    area = tmp_path_factory.mktemp("mese2")
    esegui_mese(area, 1)
    return esegui_mese(area, 2)

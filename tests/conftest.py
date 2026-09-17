import pytest

from micp_lca import load_data


@pytest.fixture(scope="session")
def data():
    return load_data()

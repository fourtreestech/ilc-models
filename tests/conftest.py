import pytest
from ilc_provider import fake


@pytest.fixture(scope="session")
def ilc_fake():
    return fake


@pytest.fixture(scope="session")
def fake_league(ilc_fake):
    return ilc_fake.league()

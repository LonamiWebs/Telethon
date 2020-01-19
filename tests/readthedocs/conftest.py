import pathlib

import pytest


@pytest.fixture
def docs_dir():
    return pathlib.Path('readthedocs')

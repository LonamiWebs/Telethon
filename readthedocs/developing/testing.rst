=====
Tests
=====

Telethon uses `Pytest <https://pytest.org/>`__, for testing, `Tox
<https://tox.readthedocs.io/en/latest/>`__ for environment setup, and
`pytest-asyncio <https://pypi.org/project/pytest-asyncio/>`__ and `pytest-cov
<https://pytest-cov.readthedocs.io/en/latest/>`__ for asyncio and 
`coverage <https://coverage.readthedocs.io/>`__ integration.

While reading the full documentation for these is probably a good idea, there
is a lot to read, so a brief summary of these tools is provided below for
convienience.

Brief Introduction to Pytest
============================

`Pytest <https://pytest.org/>`__ is a tool for discovering and running python
tests, as well as allowing modular reuse of test setup code using fixtures.

Most Pytest tests will look something like this::

    from module import my_thing, my_other_thing

    def test_my_thing(fixture):
        assert my_thing(fixture) == 42

    @pytest.mark.asyncio
    async def test_my_thing(event_loop):
        assert await my_other_thing(loop=event_loop) == 42

Note here:

 1. The test imports one specific function. The role of unit tests is to test
    that the implementation of some unit, like a function or class, works.
    It's role is not so much to test that components interact well with each
    other. I/O, such as connecting to remote servers, should be avoided. This
    helps with quickly identifying the source of an error, finding silent
    breakage, and makes it easier to cover all possible code paths.

    System or integration tests can also be useful, but are currently out of
    scope of Telethon's automated testing.

 2. A function ``test_my_thing`` is declared. Pytest searches for files
    starting with ``test_``, classes starting with ``Test`` and executes any
    functions or methods starting with ``test_`` it finds.

 3. The function is declared with a parameter ``fixture``. Fixtures are used to
    request things required to run the test, such as temporary directories,
    free TCP ports, Connections, etc. Fixtures are declared by simply adding
    the fixture name as parameter. A full list of available fixtures can be
    found with the ``pytest --fixtures`` command.

 4. The test uses a simple ``assert`` to test some condition is valid.  Pytest
    uses some magic to ensure that the errors from this are readable and easy
    to debug.

 5. The ``pytest.mark.asyncio`` fixture is provided by ``pytest-asyncio``. It
    starts a loop and executes a test function as coroutine. This should be
    used for testing asyncio code. It also declares the ``event_loop``
    fixture, which will request an ``asyncio`` event loop.

Brief Introduction to Tox
=========================

`Tox <https://tox.readthedocs.io/en/latest/>`__ is a tool for automated setup
of virtual environments for testing. While the tests can be run directly by
just running ``pytest``, this only tests one specific python version in your
existing environment, which will not catch e.g. undeclared dependencies, or
version incompatabilities.

Tox environments are declared in the ``tox.ini`` file. The default
environments, declared at the top, can be simply run with ``tox``. The option
``tox -e py36,flake`` can be used to request specific environments to be run.

Brief Introduction to Pytest-cov
================================

Coverage is a useful metric for testing. It measures the lines of code and
branches that are exercised by the tests. The higher the coverage, the more
likely it is that any coding errors will be caught by the tests.

A brief coverage report can be generated with the ``--cov`` option to ``tox``,
which will be passed on to ``pytest``. Additionally, the very useful HTML
report can be generated with ``--cov --cov-report=html``, which contains a
browsable copy of the source code, annotated with coverage information for each
line.

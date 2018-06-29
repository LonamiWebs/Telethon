#!/usr/bin/env python3
"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject

Extra supported commands are:
* gen, to generate the classes required for Telethon to run or docs
* pypi, to generate sdist, bdist_wheel, and push to PyPi
"""

import itertools
import json
import os
import re
import shutil
from codecs import open
from sys import argv

from setuptools import find_packages, setup


class TempWorkDir:
    """Switches the working directory to be the one on which this file lives,
       while within the 'with' block.
    """
    def __init__(self):
        self.original = None

    def __enter__(self):
        self.original = os.path.abspath(os.path.curdir)
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        return self

    def __exit__(self, *args):
        os.chdir(self.original)


GENERATOR_DIR = 'telethon_generator'
LIBRARY_DIR = 'telethon'

ERRORS_IN_JSON = os.path.join(GENERATOR_DIR, 'data', 'errors.json')
ERRORS_IN_DESC = os.path.join(GENERATOR_DIR, 'data', 'error_descriptions')
ERRORS_OUT = os.path.join(LIBRARY_DIR, 'errors', 'rpcerrorlist.py')

INVALID_BM_IN = os.path.join(GENERATOR_DIR, 'data', 'invalid_bot_methods.json')

TLOBJECT_IN_CORE_TL = os.path.join(GENERATOR_DIR, 'data', 'mtproto_api.tl')
TLOBJECT_IN_TL = os.path.join(GENERATOR_DIR, 'data', 'telegram_api.tl')
TLOBJECT_OUT = os.path.join(LIBRARY_DIR, 'tl')
IMPORT_DEPTH = 2

DOCS_IN_RES = os.path.join(GENERATOR_DIR, 'data', 'html')
DOCS_OUT = 'docs'


def generate(which):
    from telethon_generator.parsers import parse_errors, parse_tl, find_layer
    from telethon_generator.generators import\
        generate_errors, generate_tlobjects, generate_docs, clean_tlobjects

    # Older Python versions open the file as bytes instead (3.4.2)
    with open(INVALID_BM_IN, 'r') as f:
        invalid_bot_methods = set(json.load(f))

    layer = find_layer(TLOBJECT_IN_TL)
    errors = list(parse_errors(ERRORS_IN_JSON, ERRORS_IN_DESC))
    tlobjects = list(itertools.chain(
        parse_tl(TLOBJECT_IN_CORE_TL, layer, invalid_bot_methods),
        parse_tl(TLOBJECT_IN_TL, layer, invalid_bot_methods)))

    if not which:
        which.extend(('tl', 'errors'))

    clean = 'clean' in which
    action = 'Cleaning' if clean else 'Generating'
    if clean:
        which.remove('clean')

    if 'all' in which:
        which.remove('all')
        for x in ('tl', 'errors', 'docs'):
            if x not in which:
                which.append(x)

    if 'tl' in which:
        which.remove('tl')
        print(action, 'TLObjects...')
        if clean:
            clean_tlobjects(TLOBJECT_OUT)
        else:
            generate_tlobjects(tlobjects, layer, IMPORT_DEPTH, TLOBJECT_OUT)

    if 'errors' in which:
        which.remove('errors')
        print(action, 'RPCErrors...')
        if clean:
            if os.path.isfile(ERRORS_OUT):
                os.remove(ERRORS_OUT)
        else:
            with open(ERRORS_OUT, 'w', encoding='utf-8') as file:
                generate_errors(errors, file)

    if 'docs' in which:
        which.remove('docs')
        print(action, 'documentation...')
        if clean:
            if os.path.isdir(DOCS_OUT):
                shutil.rmtree(DOCS_OUT)
        else:
            generate_docs(tlobjects, errors, layer, DOCS_IN_RES, DOCS_OUT)

    if 'json' in which:
        which.remove('json')
        print(action, 'JSON schema...')
        mtproto = 'mtproto_api.json'
        telegram = 'telegram_api.json'
        if clean:
            for x in (mtproto, telegram):
                if os.path.isfile(x):
                    os.remove(x)
        else:
            def gen_json(fin, fout):
                methods = []
                constructors = []
                for tl in parse_tl(fin, layer):
                    if tl.is_function:
                        methods.append(tl.to_dict())
                    else:
                        constructors.append(tl.to_dict())
                what = {'constructors': constructors, 'methods': methods}
                with open(fout, 'w') as f:
                    json.dump(what, f, indent=2)

            gen_json(TLOBJECT_IN_CORE_TL, mtproto)
            gen_json(TLOBJECT_IN_TL, telegram)

    if which:
        print('The following items were not understood:', which)
        print('  Consider using only "tl", "errors" and/or "docs".')
        print('  Using only "clean" will clean them. "all" to act on all.')
        print('  For instance "gen tl errors".')


def main():
    if len(argv) >= 2 and argv[1] == 'gen':
        generate(argv[2:])

    elif len(argv) >= 2 and argv[1] == 'pypi':
        # (Re)generate the code to make sure we don't push without it
        generate(['tl', 'errors'])

        # Try importing the telethon module to assert it has no errors
        try:
            import telethon
        except:
            print('Packaging for PyPi aborted, importing the module failed.')
            return

        # Need python3.5 or higher, but Telethon is supposed to support 3.x
        # Place it here since noone should be running ./setup.py pypi anyway
        from subprocess import run
        from shutil import rmtree

        for x in ('build', 'dist', 'Telethon.egg-info'):
            rmtree(x, ignore_errors=True)
        run('python3 setup.py sdist', shell=True)
        run('python3 setup.py bdist_wheel', shell=True)
        run('twine upload dist/*', shell=True)
        for x in ('build', 'dist', 'Telethon.egg-info'):
            rmtree(x, ignore_errors=True)

    else:
        # e.g. install from GitHub
        if os.path.isdir(GENERATOR_DIR):
            generate(['tl', 'errors'])

        # Get the long description from the README file
        with open('README.rst', 'r', encoding='utf-8') as f:
            long_description = f.read()

        with open('telethon/version.py', 'r', encoding='utf-8') as f:
            version = re.search(r"^__version__\s*=\s*'(.*)'.*$",
                                f.read(), flags=re.MULTILINE).group(1)
        setup(
            name='Telethon',
            version=version,
            description="Full-featured Telegram client library for Python 3",
            long_description=long_description,

            url='https://github.com/LonamiWebs/Telethon',
            download_url='https://github.com/LonamiWebs/Telethon/releases',

            author='Lonami Exo',
            author_email='totufals@hotmail.com',

            license='MIT',

            # See https://stackoverflow.com/a/40300957/4759433
            # -> https://www.python.org/dev/peps/pep-0345/#requires-python
            # -> http://setuptools.readthedocs.io/en/latest/setuptools.html
            python_requires='>=3.5',

            # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
            classifiers=[
                #   3 - Alpha
                #   4 - Beta
                #   5 - Production/Stable
                'Development Status :: 5 - Production/Stable',

                'Intended Audience :: Developers',
                'Topic :: Communications :: Chat',

                'License :: OSI Approved :: MIT License',

                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.5',
                'Programming Language :: Python :: 3.6'
            ],
            keywords='telegram api chat client library messaging mtproto',
            packages=find_packages(exclude=[
                'telethon_*', 'run_tests.py', 'try_telethon.py'
            ]),
            install_requires=['pyaes', 'rsa',
                              'async_generator'],
            extras_require={
                'cryptg': ['cryptg']
            }
        )


if __name__ == '__main__':
    with TempWorkDir():  # Could just use a try/finally but this is + reusable
        main()

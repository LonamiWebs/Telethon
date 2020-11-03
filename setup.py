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
import sys
from pathlib import Path
from subprocess import run

from setuptools import find_packages, setup

# Needed since we're importing local files
sys.path.insert(0, os.path.dirname(__file__))

class TempWorkDir:
    """Switches the working directory to be the one on which this file lives,
       while within the 'with' block.
    """
    def __init__(self, new=None):
        self.original = None
        self.new = new or str(Path(__file__).parent.resolve())

    def __enter__(self):
        # os.chdir does not work with Path in Python 3.5.x
        self.original = str(Path('.').resolve())
        os.makedirs(self.new, exist_ok=True)
        os.chdir(self.new)
        return self

    def __exit__(self, *args):
        os.chdir(self.original)


GENERATOR_DIR = Path('telethon_generator')
LIBRARY_DIR = Path('telethon')

ERRORS_IN = GENERATOR_DIR / 'data/errors.csv'
ERRORS_OUT = LIBRARY_DIR / 'errors/rpcerrorlist.py'

METHODS_IN = GENERATOR_DIR / 'data/methods.csv'

# Which raw API methods are covered by *friendly* methods in the client?
FRIENDLY_IN = GENERATOR_DIR / 'data/friendly.csv'

TLOBJECT_IN_TLS = [Path(x) for x in GENERATOR_DIR.glob('data/*.tl')]
TLOBJECT_OUT = LIBRARY_DIR / 'tl'
IMPORT_DEPTH = 2

DOCS_IN_RES = GENERATOR_DIR / 'data/html'
DOCS_OUT = Path('docs')


def generate(which, action='gen'):
    from telethon_generator.parsers import\
        parse_errors, parse_methods, parse_tl, find_layer

    from telethon_generator.generators import\
        generate_errors, generate_tlobjects, generate_docs, clean_tlobjects

    layer = next(filter(None, map(find_layer, TLOBJECT_IN_TLS)))
    errors = list(parse_errors(ERRORS_IN))
    methods = list(parse_methods(METHODS_IN, FRIENDLY_IN, {e.str_code: e for e in errors}))

    tlobjects = list(itertools.chain(*(
        parse_tl(file, layer, methods) for file in TLOBJECT_IN_TLS)))

    if not which:
        which.extend(('tl', 'errors'))

    clean = action == 'clean'
    action = 'Cleaning' if clean else 'Generating'

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
            if ERRORS_OUT.is_file():
                ERRORS_OUT.unlink()
        else:
            with ERRORS_OUT.open('w') as file:
                generate_errors(errors, file)

    if 'docs' in which:
        which.remove('docs')
        print(action, 'documentation...')
        if clean:
            if DOCS_OUT.is_dir():
                shutil.rmtree(str(DOCS_OUT))
        else:
            in_path = DOCS_IN_RES.resolve()
            with TempWorkDir(DOCS_OUT):
                generate_docs(tlobjects, methods, layer, in_path)

    if 'json' in which:
        which.remove('json')
        print(action, 'JSON schema...')
        json_files = [x.with_suffix('.json') for x in TLOBJECT_IN_TLS]
        if clean:
            for file in json_files:
                if file.is_file():
                    file.unlink()
        else:
            def gen_json(fin, fout):
                meths = []
                constructors = []
                for tl in parse_tl(fin, layer):
                    if tl.is_function:
                        meths.append(tl.to_dict())
                    else:
                        constructors.append(tl.to_dict())
                what = {'constructors': constructors, 'methods': meths}
                with open(fout, 'w') as f:
                    json.dump(what, f, indent=2)

            for fs in zip(TLOBJECT_IN_TLS, json_files):
                gen_json(*fs)

    if which:
        print(
            'The following items were not understood:', which,
            '\n  Consider using only "tl", "errors" and/or "docs".'
            '\n  Using only "clean" will clean them. "all" to act on all.'
            '\n  For instance "gen tl errors".'
        )


def main(argv):
    if len(argv) >= 2 and argv[1] in ('gen', 'clean'):
        generate(argv[2:], argv[1])

    elif len(argv) >= 2 and argv[1] == 'pypi':
        # (Re)generate the code to make sure we don't push without it
        generate(['tl', 'errors'])

        # Try importing the telethon module to assert it has no errors
        try:
            import telethon
        except:
            print('Packaging for PyPi aborted, importing the module failed.')
            return

        remove_dirs = ['__pycache__', 'build', 'dist', 'Telethon.egg-info']
        for root, _dirs, _files in os.walk(LIBRARY_DIR, topdown=False):
            # setuptools is including __pycache__ for some reason (#1605)
            if root.endswith('/__pycache__'):
                remove_dirs.append(root)
        for x in remove_dirs:
            shutil.rmtree(x, ignore_errors=True)

        run('python3 setup.py sdist', shell=True)
        run('python3 setup.py bdist_wheel', shell=True)
        run('twine upload dist/*', shell=True)
        for x in ('build', 'dist', 'Telethon.egg-info'):
            shutil.rmtree(x, ignore_errors=True)

    else:
        # e.g. install from GitHub
        if GENERATOR_DIR.is_dir():
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
                'Programming Language :: Python :: 3.6',
                'Programming Language :: Python :: 3.7',
                'Programming Language :: Python :: 3.8',
            ],
            keywords='telegram api chat client library messaging mtproto',
            packages=find_packages(exclude=[
                'telethon_*', 'tests*'
            ]),
            install_requires=['pyaes', 'rsa'],
            extras_require={
                'cryptg': ['cryptg']
            }
        )


if __name__ == '__main__':
    with TempWorkDir():
        main(sys.argv)

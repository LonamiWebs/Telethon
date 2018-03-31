#!/usr/bin/env python3
"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject

Extra supported commands are:
* gen_tl, to generate the classes required for Garry to run
* clean_tl, to clean these generated classes
* pypi, to generate sdist, bdist_wheel, and push to PyPi
"""

# To use a consistent encoding
from codecs import open
from sys import argv, version_info
import os
import re

# Always prefer setuptools over distutils
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


ERROR_LIST = 'garry/errors/rpc_error_list.py'
ERRORS_JSON = 'garry_generator/errors.json'
ERRORS_DESC = 'garry_generator/error_descriptions'
SCHEME_TL = 'garry_generator/scheme.tl'
GENERATOR_DIR = 'garry/tl'
IMPORT_DEPTH = 2


def gen_tl(force=True):
    from garry_generator.tl_generator import TLGenerator
    from garry_generator.error_generator import generate_code
    generator = TLGenerator(GENERATOR_DIR)
    if generator.tlobjects_exist():
        if not force:
            return
        print('Detected previous TLObjects. Cleaning...')
        generator.clean_tlobjects()

    print('Generating TLObjects...')
    generator.generate_tlobjects(SCHEME_TL, import_depth=IMPORT_DEPTH)
    print('Generating errors...')
    generate_code(ERROR_LIST, json_file=ERRORS_JSON, errors_desc=ERRORS_DESC)
    print('Done.')


def main():
    if len(argv) >= 2 and argv[1] == 'gen_tl':
        gen_tl()

    elif len(argv) >= 2 and argv[1] == 'clean_tl':
        from garry_generator.tl_generator import TLGenerator
        print('Cleaning...')
        TLGenerator(GENERATOR_DIR).clean_tlobjects()
        print('Done.')

    elif len(argv) >= 2 and argv[1] == 'pypi':
        # (Re)generate the code to make sure we don't push without it
        gen_tl()

        # Try importing the garry module to assert it has no errors
        try:
            import garry
        except:
            print('Packaging for PyPi aborted, importing the module failed.')
            return

        # Need python3.5 or higher, but Garry is supposed to support 3.x
        # Place it here since noone should be running ./setup.py pypi anyway
        from subprocess import run
        from shutil import rmtree

        for x in ('build', 'dist', 'Garry.egg-info'):
            rmtree(x, ignore_errors=True)
        run('python3 setup.py sdist', shell=True)
        run('python3 setup.py bdist_wheel', shell=True)
        run('twine upload dist/*', shell=True)
        for x in ('build', 'dist', 'Garry.egg-info'):
            rmtree(x, ignore_errors=True)

    elif len(argv) >= 2 and argv[1] == 'fetch_errors':
        from garry_generator.error_generator import fetch_errors
        fetch_errors(ERRORS_JSON)

    else:
        # Call gen_tl() if the scheme.tl file exists, e.g. install from GitHub
        if os.path.isfile(SCHEME_TL):
            gen_tl(force=False)

        # Get the long description from the README file
        with open('README.rst', encoding='utf-8') as f:
            long_description = f.read()

        with open('garry/version.py', encoding='utf-8') as f:
            version = re.search(r"^__version__\s*=\s*'(.*)'.*$",
                                f.read(), flags=re.MULTILINE).group(1)
        setup(
            name='Garry',
            version=version,
            description="Full-featured Telegram client library for Python 3",
            long_description=long_description,

            url='https://github.com/LonamiWebs/Garry',
            download_url='https://github.com/LonamiWebs/Garry/releases',

            author='Lonami Exo',
            author_email='totufals@hotmail.com',

            license='MIT',

            # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
            classifiers=[
                #   3 - Alpha
                #   4 - Beta
                #   5 - Production/Stable
                'Development Status :: 3 - Alpha',

                'Intended Audience :: Developers',
                'Topic :: Communications :: Chat',

                'License :: OSI Approved :: MIT License',

                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.3',
                'Programming Language :: Python :: 3.4',
                'Programming Language :: Python :: 3.5',
                'Programming Language :: Python :: 3.6'
            ],
            keywords='telegram api chat client library messaging mtproto',
            packages=find_packages(exclude=[
                'garry_generator', 'garry_tests', 'run_tests.py',
                'try_garry.py',
                'garry_generator/parser/__init__.py',
                'garry_generator/parser/source_builder.py',
                'garry_generator/parser/tl_object.py',
                'garry_generator/parser/tl_parser.py',
            ]),
            install_requires=['pyaes', 'rsa',
                              'typing' if version_info < (3, 5, 2) else ""],
            extras_require={
                'cryptg': ['cryptg']
            }
        )


if __name__ == '__main__':
    with TempWorkDir():  # Could just use a try/finally but this is + reusable
        main()

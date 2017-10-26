#!/usr/bin/env python3
import argparse
import logging
import sys
import unittest

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def test_suite(skip_network=False):
    from telethon_tests import \
        CryptoTests, ParserTests, TLTests, UtilsTests, NetworkTests

    test_classes = [CryptoTests, ParserTests, TLTests, UtilsTests]

    if skip_network:
        log.warning("Skipping network tests")
    else:
        log.info("Running with network tests")
        test_classes.append(NetworkTests)

    loader = unittest.TestLoader()

    suites_list = []
    for test_class in test_classes:
        suite = loader.loadTestsFromTestCase(test_class)
        suites_list.append(suite)

    return unittest.TestSuite(suites_list)


def main(skip_network=False):
    big_suite = test_suite(skip_network=skip_network)
    runner = unittest.TextTestRunner()
    failures = runner.run(big_suite)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n,--skip-network', dest='skip_network',
                        action='store_true')
    args = parser.parse_args()

    main(skip_network=args.skip_network)

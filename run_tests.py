#!/usr/bin/env python3
import argparse
import logging
import unittest

logging.basicConfig(level=logging.DEBUG)
__log__ = logging.getLogger(__name__)


def test_suite(skip_network=False):
    from telethon_tests import \
        CryptoTests, ParserTests, TLTests, UtilsTests, NetworkTests

    test_classes = [CryptoTests, ParserTests, TLTests, UtilsTests]

    if skip_network:
        __log__.warning("Skipping network tests")
    else:
        __log__.info("Running with network tests")
        test_classes.append(NetworkTests)

    loader = unittest.TestLoader()

    suites_list = []
    for test_class in test_classes:
        suite = loader.loadTestsFromTestCase(test_class)
        suites_list.append(suite)

    return unittest.TestSuite(suites_list)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n,--skip-network', dest='skip_network',
                        action='store_true')
    args = parser.parse_args()

    big_suite = test_suite(skip_network=args.skip_network)
    runner = unittest.TextTestRunner()
    results = runner.run(big_suite)

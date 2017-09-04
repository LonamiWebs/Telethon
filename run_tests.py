#!/usr/bin/env python3
import unittest

if __name__ == '__main__':
    from telethon_tests import \
        CryptoTests, ParserTests, TLTests, UtilsTests, NetworkTests

    test_classes = [CryptoTests, ParserTests, TLTests, UtilsTests]

    network = input('Run network tests (y/n)?: ').lower() == 'y'
    if network:
        test_classes.append(NetworkTests)

    loader = unittest.TestLoader()

    suites_list = []
    for test_class in test_classes:
        suite = loader.loadTestsFromTestCase(test_class)
        suites_list.append(suite)

    big_suite = unittest.TestSuite(suites_list)

    runner = unittest.TextTestRunner()
    results = runner.run(big_suite)

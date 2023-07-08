from telethon._impl.crypto.factorize import factorize


def test_factorization_1() -> None:
    pq = factorize(1470626929934143021)
    assert pq == (1206429347, 1218991343)


def test_factorization_2() -> None:
    pq = factorize(2363612107535801713)
    assert pq == (1518968219, 1556064227)


def test_factorization_3() -> None:
    pq = factorize(2000000000000000006)
    assert pq == (2, 1000000000000000003)

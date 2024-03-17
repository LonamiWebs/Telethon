from math import gcd
from random import randrange


def factorize(pq: int) -> tuple[int, int]:
    """
    Factorize the given number into its two prime factors.

    The algorithm here is a faster variant of [Pollard's rho algorithm],
    published by [Richard Brent], based on
    <https://comeoncodeon.wordpress.com/2010/09/18/pollard-rho-brent-integer-factorization/>.

    [Pollard's rho algorithm]: <https://en.wikipedia.org/wiki/Pollard%27s_rho_algorithm>
    [Richard Brent]: <https://maths-people.anu.edu.au/~brent/pd/rpb051i.pdf>
    """
    if pq % 2 == 0:
        return 2, pq // 2

    y, c, m = randrange(1, pq), randrange(1, pq), randrange(1, pq)
    g = r = q = 1
    x = ys = 0

    while g == 1:
        x = y
        for _ in range(r):
            y = (pow(y, 2, pq) + c) % pq

        k = 0
        while k < r and g == 1:
            ys = y
            for _ in range(min(m, r - k)):
                y = (pow(y, 2, pq) + c) % pq
                q = q * (abs(x - y)) % pq

            g = gcd(q, pq)
            k += m

        r *= 2

    if g == pq:
        while True:
            ys = (pow(ys, 2, pq) + c) % pq
            g = gcd(abs(x - ys), pq)
            if g > 1:
                break

    p, q = g, pq // g
    return (p, q) if p < q else (q, p)

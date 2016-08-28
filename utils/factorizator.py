# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/MTProto/Crypto/Factorizator.cs
from random import randint
from math import gcd


class Factorizator:
    @staticmethod
    def find_small_multiplier_lopatin(what):
        g = 0
        for i in range(3):
            q = (randint(0, 127) & 15) + 17
            x = randint(1000000000) + 1
            y = x
            lim = 1 << (i + 18)
            for j in range(1, lim):
                a, b, c = x, x, q
                while b != 0:
                    if (b & 1) != 0:
                        c += a
                        if c >= what:
                            c -= what
                    a += a
                    if a >= what:
                        a -= what
                    b >>= 1

                x = c
                z = y - x if x < y else x - y
                g = gcd(z, what)
                if g != 1:
                    break

                if (j & (j - 1)) == 0:
                    y = x

            if g > 1:
                break

        p = what // g
        return min(p, g)

    @staticmethod
    def factorize(pq):
        divisor = Factorizator.find_small_multiplier_lopatin(pq)
        return divisor, pq // divisor

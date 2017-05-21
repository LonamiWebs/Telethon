from random import randint


class Factorization:
    @staticmethod
    def find_small_multiplier_lopatin(what):
        """Finds the small multiplier by using Lopatin's method"""
        g = 0
        for i in range(3):
            q = (randint(0, 127) & 15) + 17
            x = randint(0, 1000000000) + 1
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
                g = Factorization.gcd(z, what)
                if g != 1:
                    break

                if (j & (j - 1)) == 0:
                    y = x

            if g > 1:
                break

        p = what // g
        return min(p, g)

    @staticmethod
    def gcd(a, b):
        """Calculates the greatest common divisor"""
        while a != 0 and b != 0:
            while b & 1 == 0:
                b >>= 1

            while a & 1 == 0:
                a >>= 1

            if a > b:
                a -= b
            else:
                b -= a

        return a if b == 0 else b

    @staticmethod
    def factorize(pq):
        """Factorizes the given number and returns both the divisor and the number divided by the divisor"""
        divisor = Factorization.find_small_multiplier_lopatin(pq)
        return divisor, pq // divisor

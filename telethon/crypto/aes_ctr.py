from ctypes.util import find_library
lib = find_library('ssl')

if not lib:
    # libssl.so not found; use pyaes
    import pyaes

    class AESModeCTR:
        """Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV"""
        # TODO Maybe make a pull request to pyaes to support iv on CTR

        def __init__(self, key, iv):
            # TODO Use libssl if available
            assert isinstance(key, bytes)
            self._aes = pyaes.AESModeOfOperationCTR(key)

            assert isinstance(iv, bytes)
            assert len(iv) == 16
            self._aes._counter._counter = list(iv)

        def encrypt(self, data):
            return self._aes.encrypt(data)

        def decrypt(self, data):
            return self._aes.decrypt(data)

else:

    _libssl = ctypes.cdll.LoadLibrary(lib)

    AES_MAXNR = 14
    class AES_KEY(ctypes.Structure):
        _fields_ = [
            #uint32_t rd_key[4 * (AES_MAXNR + 1)];
            ('rd_key', ctypes.c_uint32 * (4*(AES_MAXNR + 1))),
            ('rounds', ctypes.c_uint),
        ]


    class AESModeCTR:
        """Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV"""

        def __init__(self, key, iv):
            assert isinstance(key, bytes)
            self.aeskey = AES_KEY()
            self.liv = len(iv)
            self.civ = (ctypes.c_ubyte * self.liv)(*iv)
            ckey = (ctypes.c_ubyte * len(key))(*key)
            cklen = ctypes.c_int(len(key)*8)
            _libssl.AES_set_encrypt_key(ckey, cklen,  ctypes.byref(self.aeskey))

        def encrypt(self, data):

            cin = (ctypes.c_ubyte * len(plain))(*data)
            ctlen = ctypes.c_size_t(len(data))
            cout = (ctypes.c_ubyte * len(data))()
            ccount = (ctypes.c_ubyte * self.liv)(*(b'\x00'*self.liv))
            cnum = ctypes.c_uint(0)

            _libssl.AES_ctr128_encrypt(
                ctypes.byref(cin), ctypes.byref(cout),
                ctlen,  ctypes.byref(aeskey),
                self.civ,
                ccount,
                ctypes.byref(cnum),
            )

            return bytes(cout)

        def decrypt(self, data):
            # AES-CTR is symetric
            return self.encrypt(data)

"""<aes.h>
# define AES_MAXNR 14
struct aes_key_st {
# ifdef AES_LONG
    unsigned long rd_key[4 * (AES_MAXNR + 1)];
# else
    unsigned int rd_key[4 * (AES_MAXNR + 1)];
# endif
    int rounds;
};
typedef struct aes_key_st AES_KEY;

void AES_ctr128_encrypt(const unsigned char *in, unsigned char *out,
                        size_t length, const AES_KEY *key,
                        unsigned char ivec[AES_BLOCK_SIZE],
                        unsigned char ecount_buf[AES_BLOCK_SIZE],
                        unsigned int *num);
"""

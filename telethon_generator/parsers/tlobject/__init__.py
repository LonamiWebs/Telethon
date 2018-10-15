from .tlarg import TLArg
from .tlobject import TLObject
from .parser import parse_tl, find_layer


CORE_TYPES = (
    0xbc799737,  # boolFalse#bc799737 = Bool;
    0x997275b5,  # boolTrue#997275b5 = Bool;
    0x3fedd339,  # true#3fedd339 = True;
    0x1cb5c415,  # vector#1cb5c415 {t:Type} # [ t ] = Vector t;
)

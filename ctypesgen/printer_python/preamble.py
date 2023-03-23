import ctypes
from ctypes import *  # noqa: F401, F403


def _get_ptrdiff_t():

    int_types = (ctypes.c_int16, ctypes.c_int32)
    if hasattr(ctypes, "c_int64"):
        # Some builds of ctypes apparently do not have ctypes.c_int64
        # defined; it's a pretty good bet that these builds do not
        # have 64-bit pointers.
        int_types += (ctypes.c_int64,)

    c_ptrdiff_t = None
    for t in int_types:
        if ctypes.sizeof(t) == ctypes.sizeof(ctypes.c_size_t):
            c_ptrdiff_t = t

    return c_ptrdiff_t


c_ptrdiff_t = _get_ptrdiff_t()


# As of ctypes 1.0, ctypes does not support custom error-checking
# functions on callbacks, nor does it support custom datatypes on
# callbacks, so we must ensure that all callbacks return
# primitive datatypes.
#
# Non-primitive return values wrapped with UNCHECKED won't be
# typechecked, and will be converted to ctypes.c_void_p.
def UNCHECKED(type):
    if hasattr(type, "_type_") and isinstance(type._type_, str) and type._type_ != "P":
        return type
    else:
        return ctypes.c_void_p


# ctypes doesn't have direct support for variadic functions, so we have to write
# our own wrapper class
class _variadic_function(object):
    def __init__(self, func, restype, argtypes, errcheck):
        self.func = func
        self.func.restype = restype
        self.argtypes = argtypes
        if errcheck:
            self.func.errcheck = errcheck

    def _as_parameter_(self):
        # So we can pass this variadic function as a function pointer
        return self.func

    def __call__(self, *args):
        fixed_args = []
        i = 0
        for argtype in self.argtypes:
            # Typecheck what we can
            fixed_args.append(argtype.from_param(args[i]))
            i += 1
        return self.func(*fixed_args + list(args[i:]))


# ~POINTER~

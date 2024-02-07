R"""
Auto-generated by:
ctypesgen -i demolib.h -l demolib -L . -o pydemolib.py
"""

import ctypes
from ctypes import *


# -- Begin loader template --

import sys
import ctypes
import ctypes.util
import pathlib

def _find_library(name, dirs, search_sys):
    
    if sys.platform in ("win32", "cygwin", "msys"):
        patterns = ["{}.dll", "lib{}.dll", "{}"]
    elif sys.platform == "darwin":
        patterns = ["lib{}.dylib", "{}.dylib", "lib{}.so", "{}.so", "{}"]
    else:  # assume unix pattern or plain name
        patterns = ["lib{}.so", "{}.so", "{}"]
    
    libpath = None
    for dir in dirs:
        dir = pathlib.Path(dir)
        if not dir.is_absolute():
            # NOTE joining an absolute path silently discardy the path before
            dir = (pathlib.Path(__file__).parent / dir).resolve(strict=False)
        for pat in patterns:
            libpath = dir / pat.format(name)
            if libpath.is_file():
                return str(libpath)
    
    if search_sys:
        libpath = ctypes.util.find_library(name)
    if not libpath:
        raise ImportError(f"Could not find library '{name}' (dirs={dirs}, search_sys={search_sys})")
    
    return libpath

_libs_info, _libs = {}, {}

def _register_library(name, dllclass, **kwargs):
    libpath = _find_library(name, **kwargs)
    _libs_info[name] = {"name": name, "dllclass": dllclass, **kwargs, "path": libpath}
    _libs[name] = dllclass(libpath)

# -- End loader template --


# Load library 'demolib'

_register_library(
    name = 'demolib',
    dllclass = ctypes.CDLL,
    dirs = ['.'],
    search_sys = True,
)


# -- Begin header members --

# ./demolib.h: 3
if hasattr(_libs['demolib'], 'trivial_add'):
    trivial_add = _libs['demolib']['trivial_add']
    trivial_add.argtypes = [c_int, c_int]
    trivial_add.restype = c_int

# -- End header members --

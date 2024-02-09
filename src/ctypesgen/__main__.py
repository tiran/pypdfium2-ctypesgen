"""
Command-line interface for ctypesgen
"""

import re
import sys
import shlex
import shutil
import importlib
import contextlib
import argparse
import itertools
from pathlib import Path

from ctypesgen import (
    messages as msgs,
    parser as core_parser,
    processor,
    version,
    printer_python,
    printer_json,
)


@contextlib.contextmanager
def tmp_searchpath(path):
    path = str(path)
    sys.path.insert(0, path)
    try:
        yield
    finally:
        popped = sys.path.pop(0)
        assert popped is path


def find_symbols_in_modules(modnames, outpath, anchor):
    
    # NOTE(geisserml) Concerning relative imports, I've been unable to find another way than adding the output dir's parent to sys.path, given that the module itself may contain relative imports.
    # It seems like this may be a limitation of python's import system, though technically one would imagine the output dir's path itself should be sufficient.
    
    assert isinstance(modnames, (tuple, list))  # not str
    assert isinstance(outpath, Path) and outpath.is_absolute()
    if anchor:
        assert isinstance(anchor, Path) and anchor.is_absolute()
    
    symbols = set()
    for modname in modnames:
        
        n_dots = len(modname) - len(modname.lstrip("."))
        if not n_dots > 0:
            module = importlib.import_module(modname)
        else:
            tight_anchor = outpath.parents[n_dots-1]
            if anchor == tight_anchor:
                import_path = modname
            else:
                assert anchor in tight_anchor.parents
                diff = tight_anchor.parts[len(anchor.parts):]
                import_path = ".".join(["", *diff, modname[n_dots:]])
                msgs.status_message(f"Resolved runtime import {modname!r} to compile-time {import_path!r} (rerooted from outpath to linkage anchor)")
            with tmp_searchpath(anchor.parent):
                module = importlib.import_module(import_path, anchor.name)
        
        module_syms = [s for s in dir(module) if not re.fullmatch(r"__\w+__", s)]
        assert len(module_syms) > 0, f"No symbols found in module {module.__name__!r} - linkage would be pointless"
        msgs.status_message(f"Found symbols {module_syms} in {module.__name__!r}")
        symbols.update(module_syms)
    
    return symbols


# FIXME argparse parameters are not ordered consistently...
# TODO consider BooleanOptionalAction (with compat backport)
def main(given_argv=sys.argv[1:]):
    
    parser = argparse.ArgumentParser(prog="ctypesgen")
    
    if sys.version_info < (3, 8):  # compat
        
        class ExtendAction(argparse.Action):
            def __call__(self, parser, namespace, values, option_string=None):
                items = getattr(namespace, self.dest) or []
                items.extend(values)
                setattr(namespace, self.dest, items)
        
        parser.register('action', 'extend', ExtendAction)
    
    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=version.VERSION_NUMBER,
    )

    # Parameters
    parser.add_argument(
        # do not add --include for a migration period because this previously did what is now called --system-headers
        "-i", "--headers",
        dest="headers",
        nargs="+",
        action="extend",
        type=lambda p: Path(p).resolve(),
        default=[],
        help="Sequence of header files",
    )
    parser.add_argument(
        "-l", "--library",
        metavar="LIBRARY",
        help="Link to LIBRARY",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=lambda p: Path(p).resolve(),
        metavar="FILE",
        help="Write bindings to FILE",
    )
    parser.add_argument(
        "--system-headers",
        nargs="+",
        action="extend",
        default=[],
        metavar="HEADER",
        # pypdfium2-team change: eagerly include members
        help="Include and bind against members from system header HEADER, with '.h' suffix (e.g. stdio.h, stdlib.h, python3.X/Python.h). Will be translated to a <...> style include and passed to the pre-processor. Provided for portability. If the full path is known, it may be preferable to use the regular --headers option.",
    )
    parser.add_argument(
        "-m", "--modules",
        "--link-modules",
        dest="modules",
        nargs="+",
        action="extend",
        default=[],
        metavar="MODULE",
        help="Use symbols from python module MODULE. Either as system import, or as dot-prefixed relative import. In the latter case, you have to specify the top-level package via --linkage-anchor.",
    )
    parser.add_argument(
        "--linkage-anchor",
        type=lambda p: Path(p).resolve(),
        help="The top-level package to use as anchor when importing relative linked modules at compile time. While we can deduce a narrow anchor based on output path and number of dots, this is not necessarily the package root, and would fail for higher-reaching indirect imports. Further, --no-embed-templates needs to know the package root to handle shared templates and libraries. Therefore, this option is mandatory with relative modules.",
    )
    parser.add_argument(
        "-I", "--includedirs",
        dest="include_search_paths",
        nargs="+",
        action="extend",
        default=[],
        metavar="INCLUDEDIR",
        help="add INCLUDEDIR as a directory to search for headers",
    )
    parser.add_argument(
        "-L", "--universal-libdirs",
        nargs="+",
        action="extend",
        default=[],
        metavar="LIBDIR",
        help="Add LIBDIR to the search path (both compile-time and run-time)",
    )
    parser.add_argument(
        "--compile-libdirs",
        nargs="+",
        action="extend",
        default=[],
        metavar="LIBDIR",
        help="Add LIBDIR to the compile-time library search path.",
    )
    parser.add_argument(
        "--runtime-libdirs",
        nargs="+",
        action="extend",
        default=[],
        metavar="LIBDIR",
        help="Add LIBDIR to the run-time library search path.",
    )
    parser.add_argument(
        "--no-system-libsearch",
        action="store_false",
        dest="search_sys",
        help="Deactivate fallback system library search; mandate that the library be contained in the given libdirs instead."
    )
    parser.add_argument(
        "--no-embed-templates",
        action="store_false",
        dest="embed_templates",
        help="Do not embed boilerplate code in output file (e.g. library loader). Defining --output-language to Python is a prerequisite.",
    )

    # Parser options
    parser.add_argument(
        "--cpp",
        help="The command to invoke the C preprocessor, including any necessary options. By default, we try to find a supported preprocessor automatically. Example: to always use clang, pass --cpp \"clang -E\".",
    )
    parser.add_argument(
        "-D", "--define",
        dest="cppargs",
        type=lambda n: ("-D", n),
        nargs="+",
        action="extend",
        default=[],
        metavar="NAME",
        help="Add a definition to the preprocessor via commandline",
    )
    parser.add_argument(
        "-U", "--undefine",
        dest="cppargs",
        type=lambda n: ("-U", n),
        nargs="+",
        action="extend",
        default=[],
        metavar="NAME",
        help="Instruct the preprocessor to undefine the specified macro via commandline",
    )
    parser.add_argument(
        "-X", "--no-default-cppflags",
        nargs="*",
        action="extend",
        default=None,
        metavar="ENTRY",
        help="Remove ENTRY from preprocessor defaults, e.g. -X __GNUC__ can be used to not implicitly undefine __GNUC__. If only the flag is passed but never any values, it removes all defaults.",
    )
    parser.add_argument(
        "--preproc-savepath",
        metavar="FILENAME",
        help="Save preprocessor output to the specified FILENAME",
    )
    parser.add_argument(
        "--optimize-lexer",
        action="store_true",
        help="Run the lexer in optimized mode. This mode requires write "
        "access to lextab.py file stored within the ctypesgen package.",
    )

    # Processor options
    parser.add_argument(
        "-a", "--all-headers",
        action="store_true",
        help="include symbols from all headers, including system headers",
    )
    parser.add_argument(
        "--builtin-symbols",
        action="store_true",
        help="include symbols automatically generated by the preprocessor",
    )
    parser.add_argument(
        "--no-macros",
        action="store_false",
        dest="include_macros",
        help="Don't output macros. May be overridden selectively by --symbol-rules.",
    )
    parser.add_argument(
        "--no-undefs",
        action="store_false",
        dest="include_undefs",
        help="Do not remove macro definitions as per #undef directives",
    )
    parser.add_argument(
        "--symbol-rules",
        nargs="+",
        action="extend",
        default=[],
        help="Sequence of symbol inclusion rules of format RULE=exp1|exp2|..., where RULE is one of [never, if_needed, yes], followed by a python fullmatch regular expression (multiple REs may be concatenated using the vertical line char). Will be applied in order from left to right, after dependency resolution.",
    )
    parser.add_argument(
        "--no-stddef-types",
        action="store_true",
        help="Do not support extra C types from stddef.h",
    )
    parser.add_argument(
        "--no-gnu-types",
        action="store_true",
        help="Do not support extra GNU C types",
    )
    parser.add_argument(
        "--no-python-types",
        action="store_true",
        help="Do not support extra C types built in to Python",
    )
    # TODO turn into dest="load_library" and "store_false" ?
    parser.add_argument(
        "--no-load-library",
        action="store_true",
        help="Do not try to load library during the processing"
    )

    # Printer options
    parser.add_argument(
        "--insert-files",
        dest="inserted_files",
        type=lambda p: Path(p).resolve(),
        nargs="+",
        action="extend",
        default=[],
        metavar="FILENAME",
        help="Add the contents of FILENAME to the end of the wrapper file.",
    )
    parser.add_argument(
        "--output-language",
        metavar="LANGUAGE",
        default="py",
        choices=("py", "json"),
        help="Choose output language",
    )
    parser.add_argument(
        "--dllclass",
        default="CDLL",
        choices=("CDLL", "WinDLL", "OleDLL", "pythonapi"),
        help="The ctypes library class to use. 'CDLL' corresponds to the 'cdecl' calling convention, 'WinDLL' to windows-only 'stdcall'. We do not currently support libraries with mixed calling convention. As a special case, you may use 'pythonapi' to bind against Python's C API (passing matching headers and '-l python' is a pre-requisite). 'pythonapi' implies --no-load-library.",
    )
    parser.add_argument(
        "--no-symbol-guards",
        dest="guard_symbols",
        action="store_false",
        help="Do not add hasattr(...) if-guards around binary symbols. Use when input headers and runtime binary are guaranteed to match. If missing symbols are encountered during library loading, they will be excluded from the output.",
    )
    parser.add_argument(
        "--no-macro-guards",
        dest="guard_macros",
        action="store_false",
        help="Do not wrap macros in try/except.",
    )

    # Error options
    parser.add_argument(
        "--all-errors",
        action="store_true",
        dest="show_all_errors",
        help="Display all warnings and errors even if they would not affect output.",
    )
    parser.add_argument(
        "--show-long-errors",
        action="store_true",
        help="Display long error messages instead of abbreviating error messages.",
    )
    parser.add_argument(
        "--no-macro-warnings",
        action="store_false",
        dest="show_macro_warnings",
        help="Do not print macro warnings.",
    )
    parser.add_argument(
        "--debug-level",
        default=0,
        type=int,
        help="Run ctypesgen with specified debug level (also applies to yacc parser)",
    )
    
    args = parser.parse_args(given_argv)
    
    assert args.headers or args.system_headers, "Either --headers or --system-headers required."
    if any(m.startswith(".") for m in args.modules):
        assert args.linkage_anchor and not args.embed_templates, "Linked modules require --linkage-anchor and --no-embed-templates"
    if not args.embed_templates:
        assert args.linkage_anchor, "--no-embed-templates requires --linkage-anchor"
    
    if args.cpp:
        # split while preserving quotes
        args.cpp = shlex.split(args.cpp)
    else:
        if shutil.which("gcc"):
            args.cpp = ["gcc", "-E"]
        elif shutil.which("cpp"):
            args.cpp = ["cpp"]
        elif shutil.which("clang"):
            args.cpp = ["clang", "-E"]
        else:
            raise RuntimeError("C pre-processor auto-detection failed: neither gcc nor clang available.")
    
    args.cppargs = list( itertools.chain(*args.cppargs) )
    
    # Important: must not use +=, this would mutate the original object, which is problematic when default=[] is used and ctypesgen called repeatedly from within python
    args.compile_libdirs = args.compile_libdirs + args.universal_libdirs
    args.runtime_libdirs = args.runtime_libdirs + args.universal_libdirs
    
    # Figure out what names will be defined by linked-in python modules
    args.linked_symbols = find_symbols_in_modules(args.modules, args.output, args.linkage_anchor)
    
    data = core_parser.parse(args.headers, args)
    processor.process(data, args)
    data = [(k, d) for k, d in data.output_order if d.included]
    if not data:
        raise RuntimeError("No target members found.")
    printer = {"py": printer_python, "json": printer_json}[args.output_language].WrapperPrinter
    printer(args.output, args, data, given_argv)
    
    msgs.status_message("Wrapping complete.")


if __name__ == "__main__":
    main()

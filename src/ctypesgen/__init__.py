"""
Ctypesgencore is the module that contains the main body of ctypesgen - in fact,
it contains everything but the command-line interface.

ctypesgen's job is divided into three steps:

Step 1: Parse

Ctypesgen reads the input header files and parses them. It generates a list of
function, variable, struct, union, enum, constant, typedef, and macro
descriptions from the input files. These descriptions are encapsulated as
ctypesgen.descriptions.Description objects.

The package ctypesgen.parser is responsible for the parsing stage.

Step 2: Process

Ctypesgen processes the list of descriptions from the parsing stage. This is
the stage where ctypesgen resolves name conflicts and filters descriptions using
the regexes specified on the command line. Other processing steps take place
at this stage, too. When processing is done, ctypesgen finalizes which
descriptions will be included in the output file.

The package ctypesgen.processor is responsible for the processing stage.

Step 3: Print

Ctypesgen writes the descriptions to the output file, along with a header.

The package ctypesgen.printer is responsible for the printing stage.

There are three modules in ctypesgen that describe the format that the
parser, processor, and printer modules use to pass information. They are:

* descriptions: Classes to represent the descriptions.

* ctypedecls: Classes to represent C types.

* expressions: Classes to represent an expression in a language-independent
format.
"""

# Worker modules
from . import parser
from . import processor
from . import printer_python
from . import printer_json
from . import version

# Data structure modules
from . import descriptions
from . import ctypedescs
from . import expressions

# Helper modules
from . import messages

# Entry points
from .__main__ import main, api_main

__version__ = version.VERSION.partition("-")[-1]
VERSION = __version__
PYPDFIUM2_SPECIFIC = True

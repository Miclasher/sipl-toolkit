"""SIPL Language Toolkit."""

import sys

__version__ = "0.1.0"

# SIPL integers are unbounded (textbook semantics); lift CPython's int<->str digit limit so
# literals, `run` output and JSON serialization of huge values do not fail.
sys.set_int_max_str_digits(0)

"""Open Books: financial documents in, one proven JSON document per file out, or a typed refusal.

One package, five parts: openbooks.core (the openbooks.v1 contract, normalisation, balance gates, layout registry, CLI),
openbooks.statements, openbooks.gateways, openbooks.tax (the providers) and openbooks.doctor (installation checks).
The names below are re-exported from openbooks.core; semver applies to them and to the openbooks.v1 document shape.
"""
from ._version import __version__
from .core import (SCHEMA_VERSION, EngineFault, OpenBooksError, Params, PluginLoadError, ProviderMissing, Refusal, Registry,
                   date_order, default_registry, fmt, load_schema, money, process, to_date, to_dec, validate_output)

__all__ = ["process", "Params", "Refusal", "ProviderMissing", "EngineFault", "PluginLoadError", "OpenBooksError",
           "validate_output", "load_schema", "SCHEMA_VERSION", "to_dec", "to_date", "date_order", "fmt", "money",
           "Registry", "default_registry", "__version__"]

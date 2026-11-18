"""Open Books core: the openbooks.v1 contract, Decimal normalisation, balance gates, and the layout registry.

Public API (semver applies to these names and to the openbooks.v1 document shape):
  process, Params, Refusal, validate_output, load_schema, SCHEMA_VERSION,
  to_dec, to_date, date_order, fmt, money, Registry, default_registry, ProviderMissing, EngineFault, PluginLoadError.
Everything else, including underscore names and helper modules, may change between minor versions.
"""
from .errors import EngineFault, OpenBooksError, PluginLoadError, ProviderMissing, Refusal
from .normalise import date_order, fmt, money, to_date, to_dec
from .params import Params
from .process import process
from .registry import LAYOUT_API_VERSION, Registry, default_registry
from .schema import SCHEMA_VERSION, load_schema, validate_output

__version__ = "0.1.0"
__all__ = ["process", "Params", "Refusal", "ProviderMissing", "EngineFault", "PluginLoadError", "OpenBooksError",
           "validate_output", "load_schema", "SCHEMA_VERSION", "to_dec", "to_date", "date_order", "fmt", "money",
           "Registry", "default_registry", "LAYOUT_API_VERSION", "__version__"]

"""Compatibility facade: `openbooks.pipeline` keeps working while the engine lives in openbooks-core.

New code should import from `openbooks_core` (the contract and registry) and the provider packages. Everything here is
re-exported unchanged; the names below are the ones 0.1 callers, tests and the hosted server rely on.
"""
from __future__ import annotations

import sys

from openbooks_core.builders import D, empty_data as _empty_data, settlement_batch as _settlement, statement_doc  # noqa: F401
from openbooks_core.cli import main
from openbooks_core.errors import Refusal
from openbooks_core.evidence import evidence, sha256_file
from openbooks_core.gates import run_gate as _run_gate
from openbooks_core.grade import run_eval
from openbooks_core.guard import ALLOWED_EXT, DOC_EXT, MAX_BYTES, TEXT_EXT, decode, guard
from openbooks_core.normalise import EXPONENT, YEAR_RANGE, date_order, fmt, money, norm, to_date, to_dec
from openbooks_core.params import Params
from openbooks_core.process import STAGES, dumps, process
from openbooks_core.registry import (AIS_REQ, B1099_REQ, BANK_ROLES, FIRA_REQ, HEADER_SCAN_ROWS, PAYPAL_REQ, RAZORPAY_REQ,
                                     STRIPE_REQ, TB_REQ, TDS_REQ, WISE_REQ, bank_cols, default_registry, find_header)
from openbooks_core.registry import detect as _detect
from openbooks_core.report import run_report
from openbooks_core.schema import SCHEMA_VERSION, load_schema, refusal_doc, validate_output

from .parsers_gateways import parse_razorpay, parse_stripe
from .parsers_statements import parse_bank_csv, parse_mt940, parse_ofx
from .parsers_tax import FX_TOLERANCE, fx_check

SCHEMA = load_schema()


def detect(text: str):
    """Returns (format, layout_version, parser args). Unknown layouts are refused, never guessed."""
    d = _detect(text)
    return d.format, d.layout, d.args


def run_gate(data: dict) -> list[dict]:
    return _run_gate(data, default_registry().gates())


def run_layout(layout: str, args, p: Params):
    return default_registry().run_layout(layout, args, p)


if __name__ == "__main__":
    sys.exit(main())

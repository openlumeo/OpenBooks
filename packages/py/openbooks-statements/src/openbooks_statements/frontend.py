"""PDF and image front end as a registry provider: extract() reads the document, identity() names the model that cross-checked it."""
from __future__ import annotations

from openbooks_core.errors import EngineFault

from .pdf_front import extract_document


class _DocumentFrontend:
    def extract(self, path, params):
        try:
            import fitz  # noqa: F401  (PyMuPDF reads the text layer and renders pages for OCR)
        except ImportError as e:
            raise EngineFault("PDF and image statements need PyMuPDF: pip install 'openbooks-statements[pdf]'") from e
        return extract_document(path, params)

    def identity(self, params):
        from .roles import RoleModel

        return getattr(RoleModel.load(), "identity", None)


FRONTEND = _DocumentFrontend()

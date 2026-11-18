"""PDF and image front end as a registry provider: extract() reads the document, identity() names the model that cross-checked it."""
from __future__ import annotations

from .pdf_front import extract_document


class _DocumentFrontend:
    def extract(self, path, params):
        return extract_document(path, params)

    def identity(self, params):
        from .roles import RoleModel

        return getattr(RoleModel.load(), "identity", None)


FRONTEND = _DocumentFrontend()

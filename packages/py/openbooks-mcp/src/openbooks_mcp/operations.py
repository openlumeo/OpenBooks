from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from typing import Annotated, Any, Callable, Literal

from openbooks import EngineFault, Params, process
from openbooks.core.cli import engine_info
from openbooks.core.guard import ALLOWED_EXT, MAX_BYTES
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_STEPS = 8
MAX_UPLOAD = 1024 * 1024
MAX_ENCODED_UPLOAD = ((MAX_UPLOAD + 2) // 3) * 4
MAX_RESPONSE = 48 * 1024
STEP_ENVELOPE_BYTES = 192
SAMPLE = (
    b"Date,Description,Debit,Credit,Balance\n"
    b"02/01/2026,Sample payment,100.00,,900.00\n"
    b"03/01/2026,Sample deposit,,50.00,950.00\n"
)
StepId = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]
Opening = Annotated[str, Field(max_length=32, pattern=r"^[+-]?[0-9]+(\.[0-9]+)?$")]
Document = dict[str, Any]
Documents = dict[str, Document]


def compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def _error_item(step_id: str, code: str, message: str) -> Document:
    return {"id": step_id, "error": {"code": code, "message": message}}


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: StepId
    operation: Annotated[str, Field(max_length=40)]
    arguments: dict[str, Any] = Field(default_factory=dict)


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProcessingOptions(Arguments):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    opening: Opening | None = None
    date_order: Literal["dmy", "mdy"] | None = None
    account: Annotated[str, Field(max_length=128)] | None = None
    allow_derived_opening: bool = False
    ocr: bool = True
    model: bool = False

    def params(self) -> Params:
        values = self.model_dump(include=set(ProcessingOptions.model_fields))
        if self.opening is not None:
            values["opening"] = Decimal(self.opening)
        return Params(**values)


class SampleInput(Arguments):
    opening: Opening | None = None


class FileInput(ProcessingOptions):
    path: Annotated[str, Field(min_length=1, max_length=512)]


class UploadInput(ProcessingOptions):
    filename: Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._ -]{0,127}$")]
    content_base64: Annotated[str, Field(min_length=4, max_length=MAX_ENCODED_UPLOAD)]


class DocumentInput(Arguments):
    from_step: StepId


class RecordsInput(DocumentInput):
    collection: Literal["accounts", "parties", "batches", "transactions", "claims", "assertions", "evidence"]
    offset: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    limit: Annotated[int, Field(ge=1, le=10)] = 5
    prefix: Annotated[str, Field(max_length=80)] = ""


class OperationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Operation:
    description: str
    arguments: type[Arguments]
    run: Callable[[Any, Documents, str], Document]


class Operations:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self._slots = BoundedSemaphore(2)
        self._operations = {
            "formats": Operation("List installed layouts and file limits for CSV, PDF, scans and financial exports.", Arguments, self._formats),
            "process_sample": Operation("Verify a synthetic bank statement CSV. Supply opening 1000.00 for a release.", SampleInput, self._process_sample),
            "process_upload": Operation("Verify a file sent as base64 bytes, up to 1 MiB.", UploadInput, self._process_upload),
            "records": Operation("Read a bounded page of transactions, batches, accounts, claims, assertions or evidence from an earlier step.", RecordsInput, self._records),
            "document": Operation("Return the complete released or refused JSON from an earlier step, subject to the response limit.", DocumentInput, self._document),
        }
        if self.root is not None:
            self._operations["process_file"] = Operation(
                "Verify a file at a relative path inside the user-approved local folder.", FileInput, self._process_file,
            )

    def search(self, query: str, details: bool) -> str:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        matches = []
        for name, operation in self._operations.items():
            keywords = set(re.findall(r"[a-z0-9]+", f"{name} {operation.description}".lower()))
            score = len(terms & keywords)
            if terms and not score:
                continue
            item = {"name": name, "description": operation.description}
            if details:
                item["arguments"] = operation.arguments.model_json_schema()
            matches.append((score, item))
        matches.sort(key=lambda entry: -entry[0])
        return compact({"operations": [entry[1] for entry in matches], "max_steps": MAX_STEPS})

    def execute(self, steps: list[Step]) -> str:
        if len({step.id for step in steps}) != len(steps):
            return compact({"error": {"code": "DUPLICATE_STEP", "message": "Step ids must be unique."}})
        if not self._slots.acquire(blocking=False):
            return compact({"error": {"code": "BUSY", "message": "Retry after outstanding runs finish."}})

        documents: Documents = {}
        results = []
        try:
            budget = MAX_RESPONSE - MAX_STEPS * STEP_ENVELOPE_BYTES
            for step in steps:
                item = self._run_step(step, documents)
                if len(compact(results + [item])) > budget:
                    item = _error_item(step.id, "RESPONSE_LIMIT", "Request fewer records or a smaller page.")
                results.append(item)
            return compact({"steps": results})
        finally:
            self._slots.release()

    def _run_step(self, step: Step, documents: Documents) -> Document:
        try:
            operation = self._operations.get(step.operation)
            if operation is None:
                raise OperationError("UNKNOWN_OPERATION", "Use search to find available operations.")
            parameters = operation.arguments.model_validate(step.arguments)
            return {"id": step.id, "result": operation.run(parameters, documents, step.id)}
        except ValidationError:
            return _error_item(step.id, "INVALID_ARGUMENTS", "Check the operation's argument schema with search.")
        except OperationError as exc:
            return _error_item(step.id, exc.code, str(exc))
        except (EngineFault, OSError):
            return _error_item(step.id, "ENGINE_ERROR", "The engine could not complete this operation. Check the install and input.")

    @staticmethod
    def _formats(_args: Arguments, _documents: Documents, _step: str) -> Document:
        return {
            **engine_info(),
            "extensions": sorted(ALLOWED_EXT),
            "max_file_bytes": MAX_BYTES,
            "max_upload_bytes": MAX_UPLOAD,
        }

    def _process_sample(self, args: SampleInput, documents: Documents, step: str) -> Document:
        options = Params(currency="INR", date_order="dmy", opening=Decimal(args.opening) if args.opening else None)
        return self._process_bytes(SAMPLE, "statement.csv", options, documents, step)

    def _process_file(self, args: FileInput, documents: Documents, step: str) -> Document:
        path = Path(args.path)
        if self.root is None or path.anchor or ".." in path.parts or "\0" in args.path:
            raise OperationError("INVALID_PATH", "Use a relative path within the approved folder.")
        try:
            resolved = (self.root / path).resolve(strict=True)
            if not resolved.is_relative_to(self.root) or not resolved.is_file():
                raise OperationError("INVALID_PATH", "Use a regular file within the approved folder.")
        except (OSError, RuntimeError):
            raise OperationError("INVALID_PATH", "The file path could not be resolved.") from None
        if resolved.stat().st_size > MAX_BYTES:
            raise OperationError("INPUT_LIMIT", "The local file exceeds the engine limit.")
        return self._process(resolved, args.params(), documents, step)

    def _process_upload(self, args: UploadInput, documents: Documents, step: str) -> Document:
        try:
            payload = base64.b64decode(args.content_base64, validate=True)
        except (ValueError, binascii.Error):
            raise OperationError("INVALID_ENCODING", "Supply standard base64 without a data URL prefix.") from None
        if len(payload) > MAX_UPLOAD:
            raise OperationError("INPUT_LIMIT", "The decoded file exceeds 1 MiB.")
        if Path(args.filename).suffix.lower() not in ALLOWED_EXT:
            raise OperationError("UNSUPPORTED_INPUT", "Use an extension listed by the formats operation.")
        return self._process_bytes(payload, args.filename, args.params(), documents, step)

    def _process_bytes(self, payload: bytes, filename: str, params: Params, documents: Documents, step: str) -> Document:
        with TemporaryDirectory(prefix="openbooks-mcp-") as directory:
            path = Path(directory) / filename
            path.write_bytes(payload)
            return self._process(path, params, documents, step)

    @staticmethod
    def _process(path: Path, params: Params, documents: Documents, step: str) -> Document:
        document = process(path, params, strict=True)
        documents[step] = document
        summary = {"schema_version": document["schema_version"], "status": document["status"]}
        if document["status"] == "refused":
            error = document["error"]
            return {**summary, "error": {**error, "message": error["message"][:500]}}
        return {
            **summary,
            "file": document["file"],
            "counts": {name: len(items) for name, items in document["data"].items()},
            "assertions": len(document["assertions"]),
        }

    @staticmethod
    def _document(args: DocumentInput, documents: Documents, _step: str) -> Document:
        if args.from_step not in documents:
            raise OperationError("MISSING_DOCUMENT", "Reference an earlier processing step in this batch.")
        return documents[args.from_step]

    def _records(self, args: RecordsInput, documents: Documents, step: str) -> Document:
        document = self._document(args, documents, step)
        if document["status"] != "ok":
            raise OperationError("DOCUMENT_REFUSED", "Inspect the refusal before requesting records.")
        if args.collection == "evidence":
            records = [
                {"key": key, **value} for key, value in document["evidence"].items()
                if key.startswith(args.prefix)
            ]
        else:
            source = document["assertions"] if args.collection == "assertions" else document["data"][args.collection]
            records = [record for record in source if str(record.get("id", "")).startswith(args.prefix)]
        end = args.offset + args.limit
        return {
            "collection": args.collection,
            "items": records[args.offset:end],
            "total": len(records),
            "next_offset": end if end < len(records) else None,
        }

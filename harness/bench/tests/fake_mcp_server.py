import json
import os
import sys

PROTOCOL_VERSION = "2025-06-18"
TAMPER_MARKER = "tampered"
BATCH_CLOSING = "1299.50"
TRANSACTION_COUNT = 2
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

SEARCH_TOOL = {
    "name": "search",
    "title": "Search Open Books operations",
    "description": "Find Open Books operations by keyword. Pass details true to include each operation's argument schema.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "maxLength": 160, "default": ""},
            "details": {"type": "boolean", "default": False},
        },
    },
    "annotations": READ_ONLY,
}

EXECUTE_TOOL = {
    "name": "execute",
    "title": "Verify financial documents",
    "description": (
        "Run an ordered batch of Open Books steps. Process a document, then read its records or full JSON "
        "from an earlier step id, or pass {\"$ref\":\"id.path\"} as an argument value. Set parallel for independent "
        "steps. A refused status is final."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,31}$"},
                        "operation": {"type": "string", "maxLength": 40},
                        "arguments": {"type": "object", "default": {}},
                    },
                    "required": ["id", "operation"],
                    "additionalProperties": False,
                },
            },
            "parallel": {"type": "boolean", "default": False},
            "stop_on_error": {"type": "boolean", "default": True},
        },
        "required": ["steps"],
    },
    "annotations": READ_ONLY,
}


def process_file(root, step_id, arguments, documents):
    relative = str(arguments.get("path", ""))
    if not relative or not os.path.isfile(os.path.join(root, relative)):
        return {"id": step_id, "error": {"code": "INVALID_PATH", "message": "The file path could not be resolved."}}
    name = os.path.basename(relative)
    if TAMPER_MARKER in name:
        document = {
            "schema_version": "openbooks.v1",
            "status": "refused",
            "error": {
                "code": "BALANCE_MISMATCH",
                "message": "batch-1: opening + sum(txns) = closing (expected 960.00 INR, got 950.00 INR)",
            },
        }
    else:
        document = {
            "schema_version": "openbooks.v1",
            "status": "ok",
            "file": {"detected_format": "csv", "layout_version": "bank_csv.v1", "method": "parser", "name": name},
            "counts": {"accounts": 1, "batches": 1, "claims": 0, "parties": 0, "transactions": TRANSACTION_COUNT},
            "assertions": 2,
        }
    documents[step_id] = document
    return {"id": step_id, "result": document}


def read_records(step_id, arguments, documents):
    document = documents.get(arguments.get("from_step"))
    if document is None or document["status"] != "ok":
        return {"id": step_id, "error": {"code": "DOCUMENT_REFUSED", "message": "Inspect the refusal before requesting records."}}
    collection = arguments.get("collection")
    if collection == "batches":
        items = [
            {
                "account_id": "acct-1",
                "closing": {"amount": BATCH_CLOSING, "currency": "INR"},
                "currency": "INR",
                "id": "batch-1",
                "kind": "statement",
                "opening": {"amount": "1000.00", "currency": "INR"},
                "opening_derived": False,
                "period_end": "2026-01-03",
                "period_start": "2026-01-02",
            }
        ]
    else:
        items = [
            {"amount": {"amount": "100.00", "currency": "INR"}, "date": "2026-01-02", "id": "txn-00001"},
            {"amount": {"amount": "50.00", "currency": "INR"}, "date": "2026-01-03", "id": "txn-00002"},
        ]
    return {"id": step_id, "result": {"collection": collection, "items": items, "total": len(items)}}


def run_step(root, step, documents):
    step_id = step.get("id")
    operation = step.get("operation")
    arguments = step.get("arguments") or {}
    if operation == "process_file":
        return process_file(root, step_id, arguments, documents)
    if operation == "records":
        return read_records(step_id, arguments, documents)
    return {"id": step_id, "error": {"code": "UNKNOWN_OPERATION", "message": f"Unknown operation {operation}."}}


def call_tool(root, params):
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name == "search":
        payload = {"operations": [{"name": "process_file"}, {"name": "records"}], "max_steps": 8}
    elif name == "execute":
        documents = {}
        payload = {"steps": [run_step(root, step, documents) for step in arguments.get("steps", [])]}
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool {name}."}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "structuredContent": payload}


def handle(root, message):
    method = message.get("method")
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "openbooks", "title": "Open Books", "version": "0.2.4"},
        }
    if method == "tools/list":
        return {"tools": [SEARCH_TOOL, EXECUTE_TOOL]}
    if method == "tools/call":
        return call_tool(root, message.get("params") or {})
    return None


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def main():
    root = os.getcwd()
    if "--root" in sys.argv:
        root = sys.argv[sys.argv.index("--root") + 1]
    silent_calls = os.environ.get("FAKE_MCP_SILENT") == "1"
    sys.stderr.write("fake openbooks MCP server running on stdio\n")
    sys.stderr.flush()
    for raw in sys.stdin:
        if not raw.strip():
            continue
        message = json.loads(raw)
        if "id" not in message:
            continue
        if message.get("method") == "tools/call" and silent_calls:
            continue
        result = handle(root, message)
        if result is None:
            send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Method not found"}})
        else:
            send({"jsonrpc": "2.0", "id": message["id"], "result": result})


if __name__ == "__main__":
    main()

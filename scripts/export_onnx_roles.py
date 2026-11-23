"""Export RoleNet with an experimental role head to ONNX, quantize to int8, and check parity against torch on held-out PDFs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic

from eval_agami import BASE
from openbooks.core.params import Params
from openbooks.statements.encoder import MAXLEN, NOT_MONEY, tensors, windows
from openbooks.statements.pdf_front import read_words
from openbooks.statements.roles import RoleModel

INPUTS = ["W", "S", "X", "pad", "R", "H"]
HELD_OUT_FILES = 8


def export(net, sample, path):
    torch.onnx.export(net, sample, str(path), input_names=INPUTS, output_names=["role_logits", "type_logits"],
                      opset_version=17, dynamo=False)


def window_inputs(model, files):
    for path in files:
        pages, _ = read_words(path, Params(ocr=False))
        words = [word for page in pages for word in page]
        for group in windows(words):
            yield tensors(words, group, model.dev)


def padded(batch):
    tokens = batch[0].shape[1]
    fill = (0, 0, 0, True, NOT_MONEY, 0)
    out = []
    for tensor, value in zip(batch, fill):
        tensor = tensor.cpu()
        shape = (1, MAXLEN - tokens, *tensor.shape[2:])
        if tensor.ndim == 3 and value == NOT_MONEY:
            extra = torch.zeros(shape, dtype=tensor.dtype)
            extra[..., 0] = NOT_MONEY
        else:
            extra = torch.full(shape, value, dtype=tensor.dtype)
        out.append(torch.cat([tensor, extra], dim=1))
    return tuple(out)


def feed(batch):
    return {name: tensor.numpy() for name, tensor in zip(INPUTS, padded(batch))}


def parity(net, session, model, files):
    compared, argmax_equal, worst = 0, 0, 0.0
    for batch in window_inputs(model, files):
        with torch.no_grad():
            reference = net(*batch)[0][0].numpy()
        produced = session.run(["role_logits"], feed(batch))[0][0][:len(reference)]
        compared += len(reference)
        argmax_equal += int((reference.argmax(axis=1) == produced.argmax(axis=1)).sum())
        worst = max(worst, float(np.abs(reference - produced).max()))
    return {"tokens": compared, "argmax_agreement": argmax_equal / compared, "max_abs_logit_diff": worst}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    model = RoleModel.load()
    if model is None:
        parser.error("Shipped model assets are required")
    net = model.net.cpu().eval()
    if args.head is not None:
        net.role.load_state_dict(torch.load(args.head, map_location="cpu"))
    files = sorted((BASE / "India_Bank_Statement_Digital_Type1").glob("*.pdf"))[:HELD_OUT_FILES]
    sample = next(iter(window_inputs(model, files[:1])))
    args.out.mkdir(parents=True, exist_ok=True)
    fp32, int8 = args.out / "role-net.onnx", args.out / "role-net.int8.onnx"
    export(net, padded(sample), fp32)
    quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QInt8)
    report = {"fp32_bytes": fp32.stat().st_size, "int8_bytes": int8.stat().st_size}
    for label, path in (("fp32", fp32), ("int8", int8)):
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        report[label] = parity(net, session, model, files)
    (args.out / "onnx-parity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

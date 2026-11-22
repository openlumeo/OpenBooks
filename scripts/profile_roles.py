"""Profile the typed role heads: where a request's time goes and whether the GPU is memory-bandwidth-bound.

    python scripts/profile_roles.py [--pdf path.pdf] [--out docs/PROFILE_ROLES.md]

Measures (all on the machine it runs on): peak copy bandwidth and peak matmul throughput as the roof, then stage times
for one real file (read, CPU feature build, GPU forward, calibration), a (batch, length) sweep in fp32 and fp16 with
achieved TFLOP/s, implied GB/s and arithmetic intensity against the roofline ridge, and a kernel-time split from
torch.profiler (GEMM vs everything else). fp16 is reported with set agreement against fp32; it is NOT enabled anywhere,
because the calibration was fitted on fp32 logits.
"""
from __future__ import annotations

import argparse
import copy
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [*(str(p) for p in (ROOT / "packages/py").glob("*/src")), str(ROOT / "server")]

import numpy as np  # noqa: E402
import torch  # noqa: E402
from openbooks.core.params import Params  # noqa: E402
from openbooks_server.inference import _pad, logits_batched  # noqa: E402
from openbooks.statements.encoder import D, LAYERS, MAXLEN, n_params, tensors, windows  # noqa: E402
from openbooks.statements.pdf_front import read_words  # noqa: E402
from openbooks.statements.roles import RoleModel  # noqa: E402

DEFAULT_PDF = ROOT / "data/raw/agami_indian_bank_statements/train/India_Bank_Statement_Digital_Type1/00001.pdf"
ACT_FLOATS_PER_TOKEN_LAYER = 24 * D


def sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def timeit(f, n: int = 15, warm: int = 3) -> float:
    """Mean milliseconds per call."""
    for _ in range(warm):
        f()
    sync()
    t = time.perf_counter()
    for _ in range(n):
        f()
    sync()
    return (time.perf_counter() - t) / n * 1000


def peak_bandwidth_gbs(dev) -> float:
    x = torch.empty(64 * 1024 * 1024, device=dev)
    y = torch.empty_like(x)
    ms = timeit(lambda: y.copy_(x), 20)
    return 2 * x.numel() * 4 / (ms / 1000) / 1e9


def peak_tflops(dev, dtype) -> float:
    a, b = (torch.randn(4096, 4096, device=dev, dtype=dtype) for _ in range(2))
    ms = timeit(lambda: a @ b, 10)
    return 2 * 4096**3 / (ms / 1000) / 1e12


def flops(b: int, t: int) -> float:
    per_tok = 2 * 12 * D * D * LAYERS + 4 * t * D * LAYERS
    return b * t * per_tok


def traffic_bytes(b: int, t: int, wbytes: int, w_total: int) -> float:
    """Lower-bound-ish: transformer weights once + estimated unfused activation traffic."""
    return w_total + b * t * LAYERS * ACT_FLOATS_PER_TOKEN_LAYER * wbytes


def rand_inputs(b: int, t: int, dev):
    g = torch.Generator(device="cpu").manual_seed(0)
    r = lambda hi, *s: torch.randint(0, hi, s, generator=g).to(dev)  # noqa: E731
    return (r(16000, b, t), r(500, b, t), r(1000, b, t, 4), torch.zeros(b, t, dtype=torch.bool, device=dev), r(5, b, t, 2),
            r(16000, b, t, 3))


def kernel_split(net, inp) -> tuple[list[tuple[str, float]], float, float]:
    from torch.profiler import ProfilerActivity, profile

    with torch.no_grad(), profile(activities=[ProfilerActivity.CUDA]) as prof:
        net(*inp)
        sync()
    rows = []
    for e in prof.key_averages():
        us = getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)
        if us:
            rows.append((e.key, us / 1000))
    rows.sort(key=lambda r: -r[1])
    total = sum(ms for _, ms in rows)
    gemm = sum(ms for k, ms in rows if any(s in k.lower() for s in ("gemm", "cutlass", "xmma", "cublas", "sm80", "sm86", "ampere")))
    return rows[:8], gemm, total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--out", type=Path, default=ROOT / "docs/PROFILE_ROLES.md")
    a = ap.parse_args()
    model = RoleModel.load()
    if model is None:
        sys.exit("no model weights/calibration in models/")
    dev = model.dev
    if dev.type != "cuda":
        print("WARNING: CUDA not available; bandwidth numbers below describe the CPU path")
    L: list[str] = []
    out = lambda s="": (print(s), L.append(s))  # noqa: E731

    gpu = torch.cuda.get_device_name(0) if dev.type == "cuda" else platform.processor()
    params = n_params(model.net)
    w_tf = sum(p.numel() for n, p in model.net.named_parameters() if n.startswith("enc.tf.")) * 4
    bw, tf32, tf16 = peak_bandwidth_gbs(dev), peak_tflops(dev, torch.float32), peak_tflops(dev, torch.float16)
    ridge32, ridge16 = tf32 * 1e12 / (bw * 1e9), tf16 * 1e12 / (bw * 1e9)
    out(f"# Roles heads: memory-bandwidth profile\n\nMeasured by `scripts/profile_roles.py` on {gpu}, torch {torch.__version__}. "
        f"Model: {params / 1e6:.1f}M parameters, {LAYERS} layers, width {D}, windows of at most {MAXLEN} tokens; "
        f"transformer weights {w_tf / 1e6:.0f} MB in fp32 (the 16384-row word table is gathered, not streamed).\n")
    out("## Roof (measured, not datasheet)\n")
    out("| quantity | value |\n|---|---|")
    out(f"| copy bandwidth (256 MB read+write) | {bw:.0f} GB/s |")
    out(f"| matmul fp32 4096^3 | {tf32:.1f} TFLOP/s |")
    out(f"| matmul fp16 4096^3 | {tf16:.1f} TFLOP/s |")
    out(f"| ridge point fp32 / fp16 (FLOP per byte to leave the bandwidth-bound region) | {ridge32:.0f} / {ridge16:.0f} |\n")

    pages, method = read_words(a.pdf, Params())
    words = [w for pg in pages for w in pg]
    wins = windows(words)
    t_read = timeit(lambda: read_words(a.pdf, Params()), 5, 1)
    t_prep = timeit(lambda: [tensors(words, w, dev) for w in wins], 10)
    prepared = [tensors(words, w, dev) for w in wins]
    batch = _pad(prepared, dev)
    with torch.no_grad():
        t_fwd_seq = timeit(lambda: [model.net(*p) for p in prepared])
        t_fwd_bat = timeit(lambda: model.net(*batch))
    role, vt = model.logits(words)
    t_cal = timeit(lambda: (model.role_cal.probs(role), model.type_cal.probs(vt), model.role_cal.sets(role), model.type_cal.sets(vt)))
    t_all_seq, t_all_bat = timeit(lambda: model.logits(words)), timeit(lambda: logits_batched(model, words))
    out(f"## Where one request goes: {a.pdf.name}, {len(pages)} pages, {len(words)} tokens, {len(wins)} windows, method {method}\n")
    out("| stage | ms | share of batched total |\n|---|---|---|")
    total = t_read + t_all_bat + t_cal
    for name, ms in [("read PDF words (PyMuPDF)", t_read), ("build tensors on CPU (row/column features)", t_prep),
                     ("GPU forward, batched (pre-built tensors)", t_fwd_bat), ("GPU forward, one window at a time", t_fwd_seq),
                     ("calibration probs + conformal sets", t_cal)]:
        out(f"| {name} | {ms:.1f} | {ms / total * 100:.0f}% |")
    out(f"| logits end to end, one window at a time (RoleModel.logits) | {t_all_seq:.1f} | |")
    out(f"| logits end to end, batched (inference.logits_batched) | {t_all_bat:.1f} | |\n")

    half = copy.deepcopy(model.net).half()
    out("## GPU forward sweep (random ids, masks off)\n")
    out("| batch x tokens | fp32 ms | fp32 GFLOP/s | fp32 GB/s implied | FLOP/byte | fp16 ms | fp16 GFLOP/s | fp16 speedup |\n|---|---|---|---|---|---|---|---|")
    with torch.no_grad():
        for b, t in [(1, 64), (1, 256), (1, 512), (4, 512), (8, 512)]:
            inp = rand_inputs(b, t, dev)
            m32, m16 = timeit(lambda: model.net(*inp)), timeit(lambda: half(*inp))
            fl, by = flops(b, t), traffic_bytes(b, t, 4, w_tf)
            out(f"| {b} x {t} | {m32:.2f} | {fl / m32 / 1e6:.0f} | {by / m32 / 1e6:.0f} | {fl / by:.0f} | {m16:.2f} | "
                f"{fl / m16 / 1e6:.0f} | {m32 / m16:.2f}x |")
    out("\nFLOP/byte uses an *estimated* activation traffic (24 floats per token per layer); treat it as an order of magnitude.\n")

    inp = rand_inputs(8, 512, dev)
    top, gemm, tot = kernel_split(model.net, inp)
    out("## Kernel time, 8 x 512 fp32 (torch.profiler)\n")
    out(f"GEMM kernels {gemm:.2f} ms of {tot:.2f} ms GPU time ({gemm / tot * 100:.0f}%); the rest is elementwise, norm, softmax, copies.\n")
    out("| kernel | ms |\n|---|---|")
    for k, ms in top:
        out(f"| `{k[:90]}` | {ms:.2f} |")

    h = RoleModel(half, model.role_cal, model.type_cal, dev)
    r32, _ = logits_batched(model, words)
    r16, _ = logits_batched(h, words)
    s32, s16 = model.role_cal.sets(r32), h.role_cal.sets(r16)
    same = np.mean([s32[i] == s16[i] for i in range(len(words))])
    out(f"\n## fp16 agreement on this file\n\nmax |role logit| difference {np.abs(r32 - r16).max():.4f}; "
        f"conformal role set identical for {same * 100:.2f}% of {len(words)} tokens. Not enabled: calibration is fitted on fp32.\n")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()

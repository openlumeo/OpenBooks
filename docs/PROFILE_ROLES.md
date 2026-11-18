# Roles heads: memory-bandwidth profile

Measured by `scripts/profile_roles.py` on NVIDIA GeForce RTX 3050 6GB Laptop GPU, torch 2.14.1+cu126. Model: 18.9M parameters, 6 layers, width 384, windows of at most 512 tokens; transformer weights 43 MB in fp32 (the 16384-row word table is gathered, not streamed).

## Roof (measured, not datasheet)

| quantity | value |
|---|---|
| copy bandwidth (256 MB read+write) | 157 GB/s |
| matmul fp32 4096^3 | 5.7 TFLOP/s |
| matmul fp16 4096^3 | 19.4 TFLOP/s |
| ridge point fp32 / fp16 (FLOP per byte to leave the bandwidth-bound region) | 36 / 124 |

## Where one request goes: 00001.pdf, 6 pages, 2611 tokens, 8 windows, method pdf_text

| stage | ms | share of batched total |
|---|---|---|
| read PDF words (PyMuPDF) | 101.5 | 56% |
| build tensors on CPU (row/column features) | 44.5 | 25% |
| GPU forward, batched (pre-built tensors) | 34.7 | 19% |
| GPU forward, one window at a time | 43.3 | 24% |
| calibration probs + conformal sets | 10.9 | 6% |
| logits end to end, one window at a time (RoleModel.logits) | 84.5 | |
| logits end to end, batched (inference.logits_batched) | 68.9 | |

## GPU forward sweep (random ids, masks off)

| batch x tokens | fp32 ms | fp32 GFLOP/s | fp32 GB/s implied | FLOP/byte | fp16 ms | fp16 GFLOP/s | fp16 speedup |
|---|---|---|---|---|---|---|---|
| 1 x 64 | 3.77 | 371 | 15 | 25 | 3.81 | 367 | 0.99x |
| 1 x 256 | 3.55 | 1702 | 28 | 61 | 3.87 | 1562 | 0.92x |
| 1 x 512 | 5.52 | 2408 | 28 | 85 | 3.81 | 3487 | 1.45x |
| 4 x 512 | 17.79 | 2987 | 28 | 107 | 8.36 | 6358 | 2.13x |
| 8 x 512 | 35.02 | 3036 | 27 | 112 | 14.93 | 7122 | 2.35x |

FLOP/byte uses an *estimated* activation traffic (24 floats per token per layer); treat it as an order of magnitude.

## Kernel time, 8 x 512 fp32 (torch.profiler)

GEMM kernels 138.25 ms of 159.68 ms GPU time (87%); the rest is elementwise, norm, softmax, copies.

| kernel | ms |
|---|---|
| `ampere_sgemm_128x64_tn` | 99.85 |
| `ampere_sgemm_128x128_nn` | 21.18 |
| `ampere_sgemm_128x128_tn` | 14.63 |
| `_ZN43_GLOBAL__N__bcfaaeff_10_SoftMax_cu_0af7be2120softmax_warp_forwardIfffLi9ELb0ELb1ELi32` | 7.63 |
| `_ZN2at6native53_GLOBAL__N__e58679f9_20_layer_norm_kernel_cu_3ff0b71f28vectorized_layer_nor` | 4.83 |
| `_ZN2at6native29vectorized_elementwise_kernelILi4ENS0_15CUDAFunctor_addIfEESt5arrayIPcLy3EE` | 3.44 |
| `_ZN8cublasLt8epilogue4impl12globalKernelILi8ELi32EfffLb1ELb0ELi4EEEviixPT1_18cublasLtEpilo` | 2.46 |
| `_ZN2at6native45_GLOBAL__N__26985c89_12_attention_cu_6cc79e1a33transform_bias_rescale_qkv_k` | 2.01 |

## fp16 agreement on this file

max |role logit| difference 0.0175; conformal role set identical for 99.92% of 2611 tokens. Not enabled: calibration is fitted on fp32.


## Findings (written by hand after the run above; re-running the script rewrites the tables, not this section)

1. **The heads are not memory-bandwidth-bound.** Large batches reach ~28 GB/s implied against 157 GB/s measured copy bandwidth (18%), at 85-112 FLOP per byte against an fp32 ridge of 36. GEMM is 87% of GPU kernel time and runs at ~3 of 5.7 TFLOP/s. The 43 MB of transformer weights stream in well under a millisecond; compute and kernel count dominate.
2. **Short inputs are launch-bound, not bandwidth-bound.** 1x64 and 1x256 cost the same (~3.6-3.8 ms): fixed per-kernel overhead.
3. **On a real request the GPU is the smaller part.** For a 6-page, 2611-token statement: PDF word extraction ~100 ms, CPU feature build ~45 ms (`column_heads`, `row_features`), GPU forward 35-43 ms, calibration sets ~11 ms. (Prep and forward are both inside the end-to-end logits rows.)
4. **Batching pages (done, `server/openbooks_server/inference.py`)** takes logits from 84.5 to 68.9 ms (-18%) with logits equal to the stock path within 5e-6 and identical conformal sets.
5. **fp16 is 2.35x faster on the GPU forward at 8x512** and keeps the conformal role set identical for 99.92% of tokens, but it only moves ~10 ms of a ~190 ms request and the calibration was fitted on fp32 logits. Not enabled. Upgrade path: refit the calibration on fp16 logits, then enable.
6. **Next real speedups are CPU-side:** cache `read_words` by file sha256 (the pipeline and `/v1/roles` read the same file twice if both are called), and vectorise the feature build.
7. **Accuracy caveat on this file:** the weights are trained on synthetic statements only. On this real Indian bank PDF the model abstains on 96% of tokens (`abstain_rate` in the response), which is the safe behaviour the heads are built for (they can only add refusals), but it means the endpoint's output is not useful for this layout until real redacted samples are in training.
8. **PagedAttention / speculative decoding do not apply here:** this is a bidirectional encoder run once per window. There is no KV cache and no autoregressive loop, so there is nothing to page or speculate on (docs/HANDOFF.md parks that for a future decoder).

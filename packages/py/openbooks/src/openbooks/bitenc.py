"""EXPERIMENT: bit-level token input for the typed heads (not used by the shipped pipeline).

The shipped encoder gives every word a hashed bucket. A header word never seen in training ('Payments', 'Money Out') lands in
an arbitrary bucket, so the model has nothing to generalise from. Here a token is its first CH characters as raw bits
(lower-cased UTF-8, MSB first), run through a small MLP, so words that share characters get similar vectors. The hashed word
table is removed, which also makes the model smaller. Column-header words use the same bit MLP.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn

from .encoder import D, Enc, RoleNet, column_heads

CH = 12
BITS = CH * 8 + 1


def bits_of(text: str) -> np.ndarray:
    """First CH bytes as bits plus one end-of-token bit: 1 when the whole token fit, 0 when it was cut off."""
    full = text.lower().encode("utf-8", "replace")
    head = np.unpackbits(np.frombuffer(full[:CH].ljust(CH, b"\0"), dtype=np.uint8))
    return np.concatenate([head, [len(full) <= CH]]).astype(np.uint8)


def token_bits(texts: list[str]) -> np.ndarray:
    return np.stack([bits_of(t) for t in texts]) if texts else np.zeros((0, BITS), np.uint8)


def head_index(boxes: list[list[int]], money: list[bool]) -> list[list[int]]:
    """Per token, the 1-based indices of up to 3 header tokens above it (0 = none). Reuses column_heads with indices as ids."""
    return column_heads(boxes, list(range(1, len(boxes) + 1)), money)


def gather_head_bits(tok_bits: torch.Tensor, hidx: torch.Tensor) -> torch.Tensor:
    """(B,n,BITS) token bits and (B,n,3) 1-based head indices -> (B,n,3,BITS); index 0 gives zeros."""
    zero = torch.zeros(tok_bits.shape[0], 1, tok_bits.shape[2], dtype=tok_bits.dtype, device=tok_bits.device)
    padded = torch.cat([zero, tok_bits], 1)
    return padded[torch.arange(tok_bits.shape[0], device=tok_bits.device)[:, None, None], hidx]


class BitEnc(Enc):
    def __init__(self):
        super().__init__()
        del self.word
        self.bitmlp = nn.Sequential(nn.Linear(BITS, D), nn.GELU(), nn.Linear(D, D))

    def forward(self, B, S, X, pad, R, HB):
        pos = torch.arange(B.shape[1], device=B.device)
        wd, ht = (X[..., 2] - X[..., 0]).clamp(0, 1000), (X[..., 3] - X[..., 1]).clamp(0, 1000)
        head = self.bitmlp(HB) * HB.any(-1, keepdim=True)
        x = (self.bitmlp(B) + self.shape(S) + self.xe(X[..., 0]) + self.xe(X[..., 2]) + self.ye(X[..., 1])
             + self.ye(X[..., 3]) + self.we(wd) + self.he(ht) + self.pos(pos) + self.rank(R[..., 0]) + self.nmon(R[..., 1])
             + head.sum(2))
        return self.norm(self.tf(x, src_key_padding_mask=pad))


class BitRoleNet(RoleNet):
    def __init__(self, n_roles: int, n_types: int):
        super().__init__(n_roles, n_types)
        self.enc = BitEnc()

    def forward(self, B, S, X, pad, R, HB):
        h = self.enc(B, S, X, pad, R, HB)
        return self.role(h), self.vtype(h)

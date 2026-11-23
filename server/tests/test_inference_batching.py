import types

import pytest
import torch

from openbooks_server import inference


def covered(groups: list[list[int]]) -> list[int]:
    return sorted(k for group in groups for k in group)


@pytest.mark.parametrize("lengths, cap", [
    ([512, 512, 17, 3, 400, 90, 90, 1], 4096),
    ([512] * 20, 4096),
    ([5, 9, 30, 200, 511, 2, 2, 2, 2], 1024),
    ([7], 4096),
])
def test_groups_never_exceed_token_cap(monkeypatch, lengths, cap):
    monkeypatch.setattr(inference, "PAD_MULTIPLE", 0)
    for group in inference._groups(lengths, cap):
        longest = max(lengths[k] for k in group)
        assert len(group) * inference._padded_len(longest) <= cap or len(group) == 1


@pytest.mark.parametrize("pad_multiple", [0, 32])
def test_every_window_appears_exactly_once(monkeypatch, pad_multiple):
    monkeypatch.setattr(inference, "PAD_MULTIPLE", pad_multiple)
    lengths = [512, 17, 3, 400, 90, 90, 1, 255, 33]
    assert covered(inference._groups(lengths, 1024)) == list(range(len(lengths)))


def test_padded_length_is_multiple_of_pad_multiple(monkeypatch):
    monkeypatch.setattr(inference, "PAD_MULTIPLE", 32)
    for length in (1, 31, 32, 33, 500, 512):
        assert inference._padded_len(length) % 32 == 0
        assert inference._padded_len(length) >= length


def test_pad_collates_to_multiple_and_masks_tail(monkeypatch):
    monkeypatch.setattr(inference, "PAD_MULTIPLE", 32)
    cpu = torch.device("cpu")

    def part(n: int) -> tuple:
        return (
            torch.ones(1, n, dtype=torch.long),
            torch.ones(1, n, dtype=torch.long),
            torch.zeros(1, n, 4, dtype=torch.long),
            torch.zeros(1, n, dtype=torch.bool),
            torch.zeros(1, n, 2, dtype=torch.long),
            torch.zeros(1, n, 3, dtype=torch.long),
        )

    batch = inference._pad([part(5), part(9)], cpu)
    assert batch[0].shape == (2, 32)
    assert batch[3][0, 9:].all()
    assert not batch[3][1, :9].any()


def test_pad_without_multiple_keeps_longest(monkeypatch):
    monkeypatch.setattr(inference, "PAD_MULTIPLE", 0)
    part = lambda n: (
        torch.ones(1, n, dtype=torch.long),
        torch.ones(1, n, dtype=torch.long),
        torch.zeros(1, n, 4, dtype=torch.long),
        torch.zeros(1, n, dtype=torch.bool),
        torch.zeros(1, n, 2, dtype=torch.long),
        torch.zeros(1, n, 3, dtype=torch.long),
    )
    assert inference._pad([part(5), part(9)], torch.device("cpu"))[0].shape == (2, 9)


@pytest.mark.parametrize("value", [None, "", "fp32", "bogus", "fp16"])
def test_default_and_unknown_dtype_fall_back_to_fp32(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(inference.DTYPE_ENV, raising=False)
    else:
        monkeypatch.setenv(inference.DTYPE_ENV, value)
    cpu_model = types.SimpleNamespace(net=torch.nn.Identity(), dev=torch.device("cpu"))
    assert inference._autocast_dtype(cpu_model) is None


def test_bf16_selects_autocast_dtype_on_cpu(monkeypatch):
    monkeypatch.setenv(inference.DTYPE_ENV, "BF16")
    cpu_model = types.SimpleNamespace(net=torch.nn.Identity(), dev=torch.device("cpu"))
    assert inference._autocast_dtype(cpu_model) is torch.bfloat16

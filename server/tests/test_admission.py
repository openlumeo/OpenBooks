"""Admission gate: limits at their exact boundaries, queue waits, ticket lifecycle and the OCR page estimate."""
import asyncio

import pytest

from openbooks_server.admission import Admission, Rejected, estimate_ocr_pages


async def never_disconnected() -> bool:
    return False


async def always_disconnected() -> bool:
    return True


def refusal_reason(gate: Admission, nbytes: int, pages: int) -> str:
    with pytest.raises(Rejected) as refused:
        gate.admit(nbytes, pages)
    return refused.value.reason


def test_zero_slots_refuses_even_an_idle_engine():
    gate = Admission(max_inflight=0, max_queue=0)

    assert refusal_reason(gate, 1, 0) == "queue_full"


def test_one_slot_and_empty_queue_refuses_the_second_job():
    gate = Admission(max_inflight=1, max_queue=0)
    gate.admit(1, 0)

    assert refusal_reason(gate, 1, 0) == "queue_full"


def test_one_slot_and_queue_of_one_admits_exactly_two_jobs():
    gate = Admission(max_inflight=1, max_queue=1)
    gate.admit(1, 0)
    gate.admit(1, 0)

    assert refusal_reason(gate, 1, 0) == "queue_full"
    assert gate.busy() == 2


def test_bytes_limit_admits_an_exact_fit_and_refuses_one_byte_more():
    gate = Admission(max_inflight=4, max_queue=4, max_bytes=100)
    gate.admit(60, 0)
    gate.admit(40, 0)

    assert gate.bytes == 100
    assert refusal_reason(gate, 1, 0) == "bytes"


def test_bytes_limit_always_admits_onto_an_idle_engine():
    gate = Admission(max_bytes=100)

    ticket = gate.admit(500, 0)

    assert ticket.nbytes == 500 and gate.bytes == 500


def test_ocr_page_cap_admits_an_exact_fit_and_refuses_one_page_more():
    gate = Admission(max_inflight=4, max_queue=4, max_pages=60)
    gate.admit(0, 60)

    assert refusal_reason(gate, 0, 1) == "ocr_pages"


def test_ocr_page_cap_admits_an_oversized_job_onto_an_idle_engine():
    gate = Admission(max_pages=60)

    gate.admit(0, 500)

    assert gate.pages == 500


def test_draining_refuses_new_admissions_with_reason_draining():
    gate = Admission()
    gate.start_drain()

    assert refusal_reason(gate, 1, 0) == "draining"


def test_start_drain_is_idempotent_and_reports_only_the_first_call():
    gate = Admission()

    first, second = gate.start_drain(), gate.start_drain()

    assert (first, second, gate.draining) == (True, False, True)


def test_precheck_reports_the_limit_without_reserving_anything():
    gate = Admission(max_inflight=1, max_queue=0)
    gate.admit(1, 0)

    assert gate.precheck(0) == "queue_full"
    assert gate.busy() == 1


def test_precheck_is_none_when_the_engine_has_room():
    assert Admission().precheck(10) is None


def test_releasing_twice_returns_capacity_only_once():
    gate = Admission(max_inflight=2)
    ticket = gate.admit(10, 3)

    ticket.release()
    ticket.release()

    assert (gate.running, gate.queued, gate.bytes, gate.pages) == (0, 0, 0, 0)


def test_release_after_drain_returns_capacity_and_keeps_refusing_work():
    gate = Admission(max_inflight=1, max_queue=1)
    ticket = gate.admit(10, 0)
    gate.start_drain()

    ticket.release()

    assert gate.busy() == 0 and gate.draining is True
    assert refusal_reason(gate, 1, 0) == "draining"


def test_releasing_a_queued_ticket_only_frees_its_queue_place():
    gate = Admission(max_inflight=1, max_queue=2)
    gate.admit(5, 0)
    waiting = gate.admit(7, 0)

    waiting.release()

    assert (gate.running, gate.queued, gate.bytes) == (0, 1, 5)


def test_try_start_respects_max_inflight_and_marks_the_ticket_running():
    gate = Admission(max_inflight=1, max_queue=2)
    first, second = gate.admit(1, 0), gate.admit(1, 0)

    assert gate.try_start(first) is True
    assert gate.try_start(second) is False
    assert (first.state, second.state, gate.running, gate.queued) == ("running", "queued", 1, 1)


def test_waiting_ticket_starts_once_a_slot_is_released():
    gate = Admission(max_inflight=1, max_queue=1)
    holder, waiter = gate.admit(0, 0), gate.admit(0, 0)
    gate.try_start(holder)
    holder.release()

    outcome = asyncio.run(waiter.wait_turn(never_disconnected))

    assert outcome == "ok" and waiter.state == "running"
    waiter.release()


def test_queued_ticket_is_dropped_when_the_client_disconnects():
    gate = Admission(max_inflight=1, max_queue=2)
    running, waiting = gate.admit(1, 0), gate.admit(1, 0)
    gate.try_start(running)

    outcome = asyncio.run(waiting.wait_turn(always_disconnected))
    waiting.release()

    assert outcome == "disconnected"
    assert (gate.running, gate.queued, gate.bytes) == (1, 0, 1)


def test_waiting_ticket_times_out_after_the_queue_timeout():
    gate = Admission(max_inflight=1, max_queue=1, queue_timeout=0.05)
    holder = gate.admit(0, 0)
    gate.try_start(holder)
    waiter = gate.admit(0, 0)

    outcome = asyncio.run(waiter.wait_turn(never_disconnected))
    waiter.release()

    assert outcome == "timeout"
    assert waiter.waited >= 0.05


def test_busy_counts_running_and_queued_jobs():
    gate = Admission(max_inflight=1, max_queue=2)
    gate.try_start(gate.admit(0, 0))
    gate.admit(0, 0)

    assert gate.busy() == 2


def test_from_env_reads_every_operational_limit(monkeypatch):
    values = {"OPENBOOKS_MAX_INFLIGHT": "3", "OPENBOOKS_MAX_QUEUE": "5", "OPENBOOKS_MAX_INFLIGHT_BYTES": "1000",
              "OPENBOOKS_MAX_OCR_PAGES": "7", "OPENBOOKS_RETRY_AFTER_S": "9", "OPENBOOKS_QUEUE_TIMEOUT_S": "1.5"}
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    gate = Admission.from_env()

    assert (gate.max_inflight, gate.max_queue, gate.max_bytes, gate.max_pages, gate.retry_after,
            gate.queue_timeout) == (3, 5, 1000, 7, 9, 1.5)


def test_from_env_uses_defaults_for_unset_or_non_numeric_values(monkeypatch):
    monkeypatch.delenv("OPENBOOKS_MAX_INFLIGHT", raising=False)
    monkeypatch.setenv("OPENBOOKS_MAX_QUEUE", "many")
    monkeypatch.setenv("OPENBOOKS_QUEUE_TIMEOUT_S", "")

    gate = Admission.from_env()

    assert (gate.max_inflight, gate.max_queue, gate.queue_timeout) == (2, 8, 30.0)


@pytest.mark.parametrize("suffix", [".png", ".PNG", ".jpg", ".jpeg"])
def test_image_is_estimated_as_one_ocr_page(tmp_path, suffix):
    image = tmp_path / f"scan{suffix}"
    image.write_bytes(b"not really an image")

    assert estimate_ocr_pages(image) == 1


def test_non_pdf_non_image_has_no_ocr_pages(tmp_path):
    csv = tmp_path / "bank.csv"
    csv.write_bytes(b"Date,Narration\n")

    assert estimate_ocr_pages(csv) == 0


def test_pdf_with_font_objects_is_text_and_needs_no_ocr(tmp_path):
    pdf = tmp_path / "text.pdf"
    pdf.write_bytes(b"/Font << >> /Type /Page /Type /Page")

    assert estimate_ocr_pages(pdf) == 0


def test_font_less_pdf_is_counted_by_its_page_objects(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"/Type /Page\n/Type/Page\n/Type /Pages\n")

    assert estimate_ocr_pages(pdf) == 2  # /Pages is the tree root, not a page


def test_font_less_pdf_without_page_objects_still_counts_one_page(tmp_path):
    pdf = tmp_path / "odd.pdf"
    pdf.write_bytes(b"%PDF-1.4 nothing useful")

    assert estimate_ocr_pages(pdf) == 1


def test_ocr_page_estimate_is_exact_at_the_sixty_page_cap(tmp_path):
    pdf = tmp_path / "long.pdf"
    pdf.write_bytes(b"/Type /Page " * 60)

    assert estimate_ocr_pages(pdf) == 60

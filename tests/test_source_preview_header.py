"""Unit coverage for the source-cell preview's header-row inference.

This heuristic drives the "Source cell preview" drawer's column labels
(``header_row``/``column_labels`` in ``SourcePreviewResponse``) across every
domain, OSIP and multi-source alike - see the docstring on
``_infer_header_row`` in ``api_handlers.py`` for the reasoning.
"""

from osip_dashboard.api_handlers import _infer_header_row


def _row(row_number: int, *values: object) -> dict[str, object]:
    return {"row_number": row_number, "values": list(values)}


def test_picks_the_dense_header_row_over_sparse_title_rows():
    header_rows = [
        _row(1, "СОБСТВЕННЫЙ"),
        _row(2, "на утро", "2026-07-01"),
        _row(3, "№", "Страна", "Статус страны", "Лимит, долл.США"),
        _row(4, None, None, None, None),
    ]
    header_row = _infer_header_row(header_rows)
    assert header_row is not None
    assert header_row["row_number"] == 3


def test_breaks_ties_toward_the_earlier_row_not_a_same_density_data_row():
    # Regression: two data rows (ratings for different bonds) are just as
    # text-dense as any header would be. Tie-breaking toward the *later* row
    # picked a data row and labelled columns "BBB"/"Baa3" instead of a real
    # header - reproduced live against the Holdings page before this fix.
    header_rows = [
        _row(5, None, "BBB", "Baa2", "BBB+", "Homebuilding"),
        _row(6, None, "BBB", "Baa3", "BBB", "Construction Machinery & Heavy Trucks"),
    ]
    header_row = _infer_header_row(header_rows)
    assert header_row is not None
    assert header_row["row_number"] == 5


def test_returns_none_when_no_row_has_any_text():
    header_rows = [_row(1, None, None), _row(2, 0, 0)]
    assert _infer_header_row(header_rows) is None


def test_returns_none_for_an_empty_header_band():
    assert _infer_header_row([]) is None

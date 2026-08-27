from time import perf_counter

import pytest

from osip_dashboard.ingestion import parse_osip_workbook


@pytest.mark.performance
def test_current_synchronous_workload_stays_within_parser_budget(workbook_paths):
    """Guard the explicit sync-parser assumption for today's sub-200 KiB files."""
    assert all(path.stat().st_size < 200 * 1024 for path in workbook_paths.values())
    started = perf_counter()
    snapshots = [
        parse_osip_workbook(path, portfolio_code="SOBSTV")
        for _ in range(10)
        for path in workbook_paths.values()
    ]
    elapsed = perf_counter() - started
    assert len(snapshots) == 20
    assert elapsed < 10, f"20 workbook parses took {elapsed:.3f}s"

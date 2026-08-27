from osip_dashboard.operations.capacity import ProbeSample, summarize, threshold_failures


def test_capacity_evidence_uses_nearest_rank_percentiles_and_thresholds():
    samples = [
        ProbeSample("overview", 200, float(index)) for index in range(1, 101)
    ]
    samples.append(ProbeSample("cash", 503, 150.0, "unavailable"))

    summary = summarize(samples)

    assert summary["request_count"] == 101
    assert summary["error_count"] == 1
    assert summary["latency_ms"] == {
        "p50": 51.0,
        "p95": 96.0,
        "p99": 100.0,
        "max": 150.0,
    }
    assert threshold_failures(
        summary, max_p95_ms=100, max_error_rate=0.01
    ) == []
    assert threshold_failures(
        summary, max_p95_ms=95, max_error_rate=0.009
    ) == [
        "p95 96.000 ms exceeds 95.000 ms",
        "error rate 0.009901 exceeds 0.009000",
    ]

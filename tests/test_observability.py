from pain001.observability import (
    clear_metrics_callbacks,
    emit_metric_event,
    register_metrics_callback,
)


def test_metrics_callback_receives_structured_event() -> None:
    captured = []

    def callback(event) -> None:
        captured.append(event)

    clear_metrics_callbacks()
    register_metrics_callback(callback)
    emit_metric_event("file_loaded", record_count=3, file_size_bytes=100)
    clear_metrics_callbacks()

    assert len(captured) == 1
    assert captured[0].name == "file_loaded"
    assert captured[0].attributes["record_count"] == 3


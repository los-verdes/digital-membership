from typing import TYPE_CHECKING

from member_card.monitoring import initialize_tracer

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def test_initialize_tracer(mocker: "MockerFixture"):
    mock_trace = mocker.patch("member_card.monitoring.trace")
    mock_trace.start()

    mock_trace_provider = mocker.patch("member_card.monitoring.TracerProvider")
    mock_trace_provider.start()

    initialize_tracer()
    mock_trace.set_tracer_provider.assert_called_once_with(
        mock_trace_provider.return_value
    )

    mock_trace_provider.stop()
    mock_trace.stop()

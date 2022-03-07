from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flask.testing import FlaskCliRunner
    from member_card.models import User
    from pytest_mock.plugin import MockerFixture


class TestCommands:
    def test_sync_subscriptions(
        self, runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        mock_sync_subs = mocker.patch(
            "member_card.commands.worker"
        ).sync_subscriptions_etl

        result = runner.invoke(
            args=["sync-subscriptions", "--load-all"],
        )

        assert result.exit_code == 0

        mock_sync_subs.assert_called_once_with(
            message=dict(type="cli-sync-subscriptions"),
            load_all=True,
        )

    def test_sync_order_id(self, runner: "FlaskCliRunner", mocker: "MockerFixture"):
        test_order_id = "order-id-is-test"

        mock_sync_order = mocker.patch(
            "member_card.commands.worker"
        ).sync_squarespace_order

        result = runner.invoke(
            args=["sync-order-id", test_order_id],
        )

        assert result.exit_code == 0

        mock_sync_order.assert_called_once_with(
            message=dict(order_id=test_order_id),
        )

    def test_send_distribution_email(
        self, runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        test_email = "test-user@losverd.es"

        mock_email_request = mocker.patch(
            "member_card.commands.worker"
        ).process_email_distribution_request

        result = runner.invoke(
            args=["send-email", test_email],
        )

        assert result.exit_code == 0

        mock_email_request.assert_called_once_with(
            message=dict(email_distribution_recipient=test_email),
        )

    def test_query_db_no_sqlalchemy(self, runner_without_db: "FlaskCliRunner"):
        # TODO: contrived thing for getting a conditional branch covered. Can prob be moved elsewere or dropped eventually....
        result = runner_without_db.invoke(
            args=["query-db", "this-user-aint-here"],
        )
        assert result.exit_code == 1

    def test_query_db_no_user_match(self, runner: "FlaskCliRunner"):
        result = runner.invoke(
            args=["query-db", "this-user-aint-here"],
        )
        assert result.exit_code == 0
        assert result.return_value is None

    def test_query_db_user_match(self, runner: "FlaskCliRunner", fake_user: "User"):
        result = runner.invoke(
            args=["query-db", fake_user.email],
        )

        assert result.exit_code == 0
        assert fake_user.email in result.output

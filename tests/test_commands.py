from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flask.testing import FlaskCliRunner
    from member_card.models import User


class TestCommands:
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

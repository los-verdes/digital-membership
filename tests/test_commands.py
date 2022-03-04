from member_card import commands

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskCliRunner

    from member_card.models import User


class TestCommands:
    def test_query_db_no_user_match(self, runner: "FlaskCliRunner"):
        result = runner.invoke(
            cli=commands.query_db,
            args=["this-user-aint-here"],
        )
        assert result.return_value is None

    def test_query_db_user_match(self, runner: "FlaskCliRunner", fake_user: "User"):
        result = runner.invoke(
            cli=commands.query_db,
            args=[fake_user.email],
        )
        assert fake_user.email in result.output

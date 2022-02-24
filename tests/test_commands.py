from member_card import commands


class TestCommands:
    def test_query_db(self, fake_user, runner_without_db):
        result = runner_without_db.invoke(
            cli=commands.query_db,
            args=[fake_user.email],
        )
        assert result

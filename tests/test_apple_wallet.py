from typing import TYPE_CHECKING
from member_card.passes import apple_wallet

if TYPE_CHECKING:
    from flask import Flask
    from pathlib import Path


def test_tmp_apple_developer_key(app: "Flask", tmpdir: "Path"):
    test_filepath_content = "this is a secret developer key!"

    k = tmpdir / "fake_apple_developer.key"
    k.write_text(test_filepath_content, encoding="utf-8")

    app.config["APPLE_KEY_FILEPATH"] = k

    with app.app_context():
        with apple_wallet.tmp_apple_developer_key() as key_filepath:
            with open(key_filepath, "r") as fp:
                assert fp.read() == test_filepath_content

    app.config["APPLE_KEY_FILEPATH"] = ""

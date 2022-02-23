import pytest
from member_card import create_app

from member_card.worker import worker_bp
import flask_migrate
from member_card.models.user import User, Role
from tests import utils
from mock import patch, Mock


@pytest.fixture(scope="session")
def app():
    app = create_app(env="tests")
    with app.app_context():
        flask_migrate.upgrade()

    app.register_blueprint(worker_bp)

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def authenticated_client(app):
    # with client.session_transaction() as session:
    #     # set a user id without going through the login route
    #     session["user_id"] = 1

    # # session is saved now

    user = utils.create_fake_user(User, roles=utils.create_fake_role(Role, "basic"))
    # utils.set_current_user(login_manager, user)
    mock_get_user = patch("flask_login.utils._get_user", Mock(return_value=user))

    with app.app_context():
        app.login_manager._login_disabled = True
        mock_get_user.start()
        yield app.test_client()
        mock_get_user.stop()
        app.login_manager._login_disabled = False


# @pytest.fixture(scope="session")
# def worker_app(app):
#     # worker_app = create_worker_app(env="tests")
#     # with worker_app.app_context():
#     # flask_migrate.upgrade()

#     app.register_blueprint(worker_bp)

#     yield app

#     # clean up / reset resources here


# @pytest.fixture()
# def worker_client(worker_app):
#     return worker_app.test_client()

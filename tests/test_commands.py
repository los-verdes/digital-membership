from typing import TYPE_CHECKING
from member_card.models import User, AnnualMembership
from member_card.db import db

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskCliRunner
    from member_card.models import MembershipCard, Role
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

    def test_update_sendgrid_template_cli(
        self, runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        mock_update_sendgrid_template = mocker.patch(
            "member_card.commands.update_sendgrid_template"
        )

        result = runner.invoke(
            args=["update-sendgrid-template"],
        )

        assert result.exit_code == 0

        mock_update_sendgrid_template.assert_called_once()

    def test_generate_card_image_cli(
        self,
        app: "Flask",
        runner: "FlaskCliRunner",
        fake_user: "User",
        mocker: "MockerFixture",
    ):
        mock_get_card = mocker.patch(
            "member_card.commands.get_or_create_membership_card"
        )
        mock_gen_card_image = mocker.patch("member_card.commands.generate_card_image")

        result = runner.invoke(
            args=["generate-card-image", fake_user.email],
        )

        assert result.exit_code == 0

        mock_get_card.assert_called_once_with(user=fake_user)
        mock_gen_card_image.assert_called_once_with(
            membership_card=mock_get_card.return_value,
            output_path=app.config["BASE_DIR"],
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

    def test_query_order_num(
        self, runner: "FlaskCliRunner", fake_membership_order: "AnnualMembership"
    ):
        result = runner.invoke(
            args=["query-order-num", fake_membership_order.order_number],
        )

        assert result.exit_code == 0
        assert str(fake_membership_order.id) in result.output

    def test_insert_google_pass_class(
        self,
        runner: "FlaskCliRunner",
        mocker: "MockerFixture",
    ):
        mock_gpay = mocker.patch("member_card.commands.gpay")

        result = runner.invoke(
            args=["insert-google-pass-class"],
        )

        assert result.exit_code == 0

        mock_gpay.modify_pass_class.assert_called_once_with(operation="insert")

    def test_update_google_pass_class(
        self,
        runner: "FlaskCliRunner",
        mocker: "MockerFixture",
    ):
        mock_gpay = mocker.patch("member_card.commands.gpay")

        result = runner.invoke(
            args=["update-google-pass-class"],
        )

        assert result.exit_code == 0

        mock_gpay.modify_pass_class.assert_called_once_with(operation="patch")

    def test_apple_serial_num_to_hex(
        self,
        runner: "FlaskCliRunner",
        fake_card: "MembershipCard",
    ):
        result = runner.invoke(
            args=["apple-serial-num-to-hex", fake_card.apple_pass_serial_number],
        )

        assert result.exit_code == 0
        assert str(fake_card.serial_number) in result.stdout

    def test_publish_sync_subscriptions_msg(
        self,
        app: "Flask",
        runner: "FlaskCliRunner",
        mocker: "MockerFixture",
    ):
        mock_publish_message = mocker.patch("member_card.commands.publish_message")

        result = runner.invoke(
            args=["publish-sync-subscriptions-msg"],
        )

        assert result.exit_code == 0

        mock_publish_message.assert_called_once_with(
            project_id=app.config["GCLOUD_PROJECT"],
            topic_id=app.config["GCLOUD_PUBSUB_TOPIC_ID"],
            message_data=dict(
                type="sync_subscriptions_etl",
            ),
        )

    def test_add_memberships_to_user_email(
        self,
        app: "Flask",
        runner: "FlaskCliRunner",
        fake_membership_order: "AnnualMembership",
        fake_other_user: "User",
    ):
        with app.app_context():
            db.session.add(fake_membership_order)
            order_email = fake_membership_order.user.email
            new_test_email = fake_other_user.email

        result = runner.invoke(
            args=["add-memberships-to-user-email", order_email, new_test_email],
        )

        assert result.exit_code == 0

        with app.app_context():
            updated_fake_order = AnnualMembership.query.filter_by(
                order_number=fake_membership_order.order_number
            ).one()
            assert updated_fake_order.user.email == new_test_email

    def test_update_user_name(
        self,
        app: "Flask",
        runner: "FlaskCliRunner",
        fake_user: "User",
    ):
        new_first_name = "You done"
        new_last_name = "Been Edited"
        new_fullname = f"{new_first_name} {new_last_name}"

        result = runner.invoke(
            args=["update-user-name", fake_user.email, new_first_name, new_last_name],
        )

        assert result.exit_code == 0

        with app.app_context():
            db.session.add(fake_user)
            updated_fake_user = User.query.filter_by(id=fake_user.id).one()
            assert updated_fake_user.first_name == new_first_name
            assert updated_fake_user.last_name == new_last_name
            assert updated_fake_user.fullname == new_fullname

    def test_add_role_to_user(
        self,
        app: "Flask",
        runner: "FlaskCliRunner",
        fake_user: "User",
        fake_admin_role: "Role",
    ):
        with app.app_context():
            db.session.add(fake_user)
            db.session.add(fake_admin_role)
            assert fake_user.has_role(fake_admin_role) is False
        result = runner.invoke(
            args=["add-role-to-user", fake_user.email, fake_admin_role.name],
        )

        assert result.exit_code == 0

        with app.app_context():
            updated_fake_user = User.query.filter_by(id=fake_user.id).one()
            assert updated_fake_user.has_role(fake_admin_role)


class TesBigcommCommands:
    def test_bigcommerce_load_single_order(
        self, app: "Flask", runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        membership_skus = app.config["BIGCOMMERCE_MEMBERSHIP_SKUS"]
        mock_bigcommerce = mocker.patch("member_card.commands.bigcommerce")
        fake_order_id = "12345"
        result = runner.invoke(
            args=["bigcomm", "load-single-order", fake_order_id],
        )

        mock_bigcommerce.load_single_order.assert_called_once_with(
            bigcommerce_client=mock_bigcommerce.get_app_client_for_store.return_value,
            membership_skus=membership_skus,
            order_id=fake_order_id,
        )
        assert result.exit_code == 0

    def test_bigcommerce_list_webhooks(
        self, app: "Flask", runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        mock_bigcommerce = mocker.patch("member_card.commands.bigcommerce")
        mock_bigcomm_client = mock_bigcommerce.get_app_client_for_store.return_value

        result = runner.invoke(
            args=["bigcomm", "list-webhooks"],
        )
        mock_bigcomm_client.Webhooks.all.assert_called_once()
        assert result.exit_code == 0

    def test_ensure_order_webhook_no_extant_hooks(
        self, app: "Flask", runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        mock_bigcommerce = mocker.patch("member_card.commands.bigcommerce")
        mock_bigcomm_client = mock_bigcommerce.get_app_client_for_store.return_value

        result = runner.invoke(
            args=["bigcomm", "ensure-order-webhook"],
        )

        mock_bigcommerce.generate_webhook_token.assert_called_once()
        mock_bigcomm_client.Webhooks.create.assert_called_once()
        assert result.exit_code == 0

    def test_bigcommerce_sync_customers(
        self, app: "Flask", runner: "FlaskCliRunner", mocker: "MockerFixture"
    ):
        mock_worker = mocker.patch("member_card.commands.worker")
        result = runner.invoke(
            args=["bigcomm", "sync-customers"],
        )

        mock_worker.sync_customers_etl.assert_called_once()
        assert result.exit_code == 0

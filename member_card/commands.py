#!/usr/bin/env python
import logging

import click
from sqlalchemy.exc import NoResultFound
from sqlalchemy.sql import func
from flask import url_for
from member_card import worker

from member_card import bigcommerce
from member_card.app import app
from member_card.db import db
from member_card.gcp import get_bucket, publish_message
from member_card.image import generate_card_image
from member_card.minibc import Minibc, parse_subscriptions
from member_card.models import AnnualMembership, User
from member_card.models.membership_card import get_or_create_membership_card
from member_card.models.user import add_role_to_user_by_email, edit_user_name
from member_card.passes import gpay
from member_card.sendgrid import update_sendgrid_template

logger = logging.getLogger(__name__)


@app.cli.group()
def cards():
    pass


@cards.command("detect-missing-card-images")
def cards_detect_missing_card_images():
    image_bucket = get_bucket()
    users = User.query.all()
    users_missing_card_image = []
    users_with_card_image = []
    for num, user in enumerate(users):
        membership_card = get_or_create_membership_card(
            user=user,
        )
        blob = image_bucket.blob(membership_card.remote_image_path)
        if blob.exists():
            users_with_card_image.append(user)
        else:
            users_missing_card_image.append(user)
        if users_missing_card_image:
            break
    print(f"#{len(users_missing_card_image)} => {users_missing_card_image}")
    print(f"#{len(users_with_card_image)}")
    topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
    for user_missing_card_image in users_missing_card_image:
        logger.info(
            f"publishing ensure_uploaded_card_image_request message for {user_missing_card_image} to pubsub {topic_id=}"
        )
        publish_message(
            project_id=app.config["GCLOUD_PROJECT"],
            topic_id=topic_id,
            message_data=dict(
                type="ensure_uploaded_card_image_request",
                member_email_address=user_missing_card_image.email,
            ),
        )


@app.cli.command("sync-subscriptions")
@click.option("--load-all/--no-load-all", default=False)
def sync_subscriptions(load_all):
    etl_results = worker.sync_subscriptions_etl(
        message=dict(type="cli-sync-subscriptions"),
        load_all=load_all,
    )
    logger.info(f"sync_subscriptions() => {etl_results=}")


@app.cli.command("sync-order-id")
@click.argument("order_id")
def sync_order_id(order_id):
    sync_order_result = worker.sync_squarespace_order(
        message=dict(order_id=order_id),
    )
    logger.info(f"sync_order_id() => {sync_order_result=}")


@app.cli.command("send-email")
@click.argument("email")
def send_distribution_email(email):
    worker.process_email_distribution_request(
        message=dict(email_distribution_recipient=email)
    )


@app.cli.command("update-sendgrid-template")
def update_sendgrid_template_cli():
    update_sendgrid_template()


@app.cli.command("generate-card-image")
@click.argument("email")
def generate_card_image_cli(email):
    user = User.query.filter_by(email=email).one()
    membership_card = get_or_create_membership_card(
        user=user,
    )
    output_path = app.config["BASE_DIR"]
    logger.info(f"Generating image of {membership_card=} for {user=} to {output_path=}")
    generate_card_image(
        membership_card=membership_card,
        output_path=output_path,
    )


@app.cli.command("query-db")
@click.argument("email")
def query_db(email):
    memberships = (
        AnnualMembership.query.filter_by(customer_email=func.lower(email))
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )

    logger.info(f"memberships matching {email}:\n{memberships}")
    # logger.info(f"{User.query.all()=}")
    try:
        user = User.query.filter_by(email=func.lower(email)).one()
        print(f"User matching {email} found!: {user=}")
        logger.info(f"user matching {email}:\n{user}")
        logger.info(f"user roles {email}:\n{user.roles}")
        logger.info(f"user memberships:\n{user.annual_memberships}")
        logger.info(f"user membership cards:\n{user.membership_cards}")
        return user
    except NoResultFound as err:
        logger.warning(f"No user found matching {email=} ({err=})")
        return None


@app.cli.command("query-order-num")
@click.argument("order_num")
def query_order_num(order_num):
    memberships = (
        AnnualMembership.query.filter_by(order_number=order_num)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )
    print(f"memberships matching {order_num}:\n{memberships}")
    users = [m.user for m in memberships]
    logger.info(f"user matching {order_num}:\n{users}")
    for user in users:
        logger.info(f"user memberships:\n{user.annual_memberships}")
        logger.info(f"user membership cards:\n{user.membership_cards}")


@app.cli.command("insert-google-pass-class")
def insert_google_pass_class():
    return gpay.modify_pass_class(operation="insert")


@app.cli.command("update-google-pass-class")
def update_google_pass_class():
    return gpay.modify_pass_class(operation="patch")


@app.cli.command("apple-serial-num-to-hex")
@click.argument("serial_num")
def apple_serial_num_to_hex(serial_num):
    from uuid import UUID

    print(UUID(int=int(serial_num)))


@app.cli.command("publish-sync-subscriptions-msg")
def publish_sync_subscriptions_msg():
    topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
    logger.info(f"publishing sync_subscriptions_etl message to pubsub {topic_id=}")
    publish_message(
        project_id=app.config["GCLOUD_PROJECT"],
        topic_id=topic_id,
        message_data=dict(
            type="sync_subscriptions_etl",
        ),
    )


@app.cli.command("add-memberships-to-user-email")
@click.argument("order_email")
@click.argument("user_email")
def add_memberships_to_user_email(order_email, user_email):
    logger.debug(f"{order_email=} => {user_email=}")
    memberships = (
        AnnualMembership.query.filter_by(customer_email=order_email)
        .order_by(AnnualMembership.created_on.desc())
        .all()
    )
    logger.debug(f"memberships matching {order_email}: {memberships}")

    user = User.query.filter_by(email=user_email).one()
    logger.debug(f"user returned for {user_email}: {user=}")
    logger.info(f"Adding memberships orders from {order_email} to: {user_email}")
    for membership in memberships:
        logger.debug(
            f"setting user_id attribute on {membership=} from {membership.user_id} to: {user.id}"
        )
        setattr(membership, "user_id", user.id)
        db.session.add(membership)
        db.session.commit()


@app.cli.command("update-user-name")
@click.argument("user_email")
@click.argument("first_name")
@click.argument("last_name")
def update_user_name(user_email, first_name, last_name):
    logger.debug(f"{user_email=} => {first_name=} {last_name=}")

    user = User.query.filter_by(email=func.lower(user_email)).one()
    logger.debug(f"user returned for {user_email}: {user=}")

    edit_user_name(
        user=user,
        new_first_name=first_name,
        new_last_name=last_name,
    )


@app.cli.command("add-role-to-user")
@click.argument("user_email")
@click.argument("role_name")
def add_role_to_user_cmd(user_email, role_name):
    logger.debug(f"{user_email=} => {role_name=}")
    role = add_role_to_user_by_email(
        user_email=user_email,
        role_name=role_name,
    )
    logger.debug(f"{role=}")
    return role


@app.cli.group()
def slack():
    pass


@slack.command("run-members-etl")
def run_slack_members_etl():
    from member_card import slack

    slack_client = slack.get_web_client()
    result = slack.slack_members_etl(
        client=slack_client,
    )
    print(f"{result=}")


@app.cli.group()
def minibc():
    pass


@minibc.command("list-incoming-webhooks")
def list_incoming_webhooks():
    minibc = Minibc(api_key=app.config["MINIBC_API_KEY"])
    webhooks_resp = minibc.get_notification_webhooks()
    print(f"{webhooks_resp=}")
    breakpoint()


@minibc.command("lookup-sub-by-order-id")
@click.argument("order_id")
def lookup_sub_by_order_id(order_id):
    minibc = Minibc(api_key=app.config["MINIBC_API_KEY"])
    subscription_order = minibc.search_subscriptions(order_id=order_id)
    print(f"{subscription_order=}")
    # breakpoint()

    # resp = minibc.perform_request(method="get",  path="subscriptions/3391663")


@minibc.command("lookup-subs-by-emails")
@click.argument("emails")
def lookup_sub_by_order_email(emails):
    minibc = Minibc(api_key=app.config["MINIBC_API_KEY"])
    for email in [e.strip() for e in emails.split(",")]:
        subscriptions = minibc.search_subscriptions(email=email)
        # subscription_order = minibc.search_subscriptions()
        print(f"*** New Store Orders for: {email} ***")
        for subscription in subscriptions:
            print(f"- ID: {subscription['id']}")
            print(f"- Status: {subscription['status']}")
            print(f"- Signup Date: {subscription['signup_date']}")
            print(f"- Payment Method: {subscription['payment_method']['method']}")
            print(f"- Next Payment Date: {subscription['next_payment_date']}")
            print(f"- Cancellation Date: {subscription['cancellation_date']}")
            print(f"- Last Modified: {subscription['last_modified']}")
        user = User.query.filter_by(email=func.lower(email)).one()
        print(f"*** Historical / Tracked Info: {email} ***")
        if user:
            print(f"\n\nMatching card.losverd.es Metadata For: {email}")
            print(f"- User: {user=}")
            print(f"- Roles: {user.roles}")
            print()
            print("All Memberships:")
            for annual_membership in user.annual_memberships:
                print(f"- {annual_membership}")
            print()
            print()


@minibc.command("sync-sub-by-email")
@click.argument("email")
def sync_sub_by_order_email(email):
    minibc = Minibc(api_key=app.config["MINIBC_API_KEY"])
    subscriptions = minibc.search_subscriptions(email=email)
    # subscription_order, last_page_num = minibc.search_subscriptions()
    print(f"{subscriptions=}")
    if subscriptions is not None:
        memberships = parse_subscriptions(
            skus=app.config["MINIBC_MEMBERSHIP_SKUS"],
            subscriptions=subscriptions,
        )
        print(f"After parsing {len(subscriptions)} subscription(s):\n{memberships=}")
    else:
        print(f"no subscription found for {email=}")
    # breakpoint()


@app.cli.group()
def bigcomm():
    pass


@bigcomm.command("ensure-scripts")
@click.argument("store_hash")
def bigcommerce_ensure_scripts(store_hash):
    from member_card import bigcommerce

    requisite_scripts = {
        "bigcommerce_membership_card.min.js": dict(
            name="LV Membership Cards",
            description="Adds customer-specific dynamic content for the Los Verdes membership status widget.",
        )
    }
    missing_script_filenames = set(requisite_scripts.keys())
    # missing_scripts =

    app_client = bigcommerce.get_bespoke_client_for_store()
    get_all_scripts_resp = app_client.get_all_scripts()
    print(f"{get_all_scripts_resp=}")

    for num, script in enumerate(get_all_scripts_resp.json()["data"]):
        script_filename = script.get("src", "/").split("/")[-1]
        print(f"script_num_{num}: {script=}")
        print(f"script_num_{num}: {missing_script_filenames=}")
        print(f"script_num_{num}: {script_filename=}")

        missing_script_filenames -= set(script_filename)

        print(f"script_num_{num}: {missing_script_filenames=}")

    for missing_script_filename in missing_script_filenames:
        missing_script = requisite_scripts[missing_script_filename]
        try:
            create_script_resp = app_client.create_a_script(
                name=missing_script["name"],
                description=missing_script["description"],
                src_filename=missing_script_filename,
            )
        except Exception as err:
            logger.error(f"{err=} => {err.response.text}")
            breakpoint()
            logger.error(f"{err=}")
        breakpoint()
        print(
            f"{missing_script_filename=}: {create_script_resp} => {create_script_resp.text=}"
        )
        breakpoint()


@bigcomm.command("ensure-widget-placement")
@click.argument("widget_name", default="membership_info")
@click.argument("region_name", default="membership_info")
def bigcommerce_ensure_widget_placement(
    # widget_uuid='6a7028ed-5d40-4630-b0c4-465e4ea73a65',
    widget_name,
    region_name,
):
    print(f"bigcommerce_ensure_widget_placement(): {widget_name=}")
    app_client = bigcommerce.get_bespoke_client_for_store()

    get_all_widgets_resp = app_client.get_all_widgets()
    print(f"{get_all_widgets_resp=}")
    # breakpoint()
    all_widgets = get_all_widgets_resp.json()["data"]
    widget_ids_by_name = {w["name"]: w["uuid"] for w in all_widgets}
    print(f"{widget_ids_by_name=}")
    widget_uuid = widget_ids_by_name.get(widget_name)

    get_all_placements_resp = app_client.get_all_placements()
    print(f"{get_all_placements_resp=}")

    all_placements = get_all_placements_resp.json()["data"]
    extant_placements_by_location = {
        d["template_file"]: d
        for d in all_placements
        if d["widget"]["name"] == widget_name
    }
    print(f"{extant_placements_by_location=}")

    requisite_placements = [
        # "pages/home",
        # "pages/account/inbox",
        # "pages/account/orders/all",
        "pages/custom/category/membership",
        "pages/custom/product/membership",
    ]
    for requisite_placement in requisite_placements:
        if extant_placement := extant_placements_by_location.get(requisite_placement):
            placement_uuid = extant_placement["uuid"]
            delete_placement_resp = app_client.delete_a_placement(
                placement_uuid=placement_uuid,
            )
            print(f"{requisite_placement=} ==> {delete_placement_resp=}")
            # update_placement_resp = app_client.update_a_placement(
            #     placement_uuid=placement_uuid,
            #     template_file=requisite_placement,
            #     widget_uuid=widget_uuid,
            #     rregion=region_name,
            # )
            # print(f"{requisite_placement=} ==> {update_placement_resp=}")
        else:
            try:
                if widget_uuid is None:
                    widget_uuid = "2871acf4-aa47-425c-bccc-25df8b907b4d"
                create_placement_resp = app_client.create_a_placement(
                    template_file=requisite_placement,
                    widget_uuid=widget_uuid,
                    region=region_name,
                )
                print(f"{requisite_placement=} ==> {create_placement_resp=}")
            except Exception as err:
                print(f"{err=}")
                print(f"{err.response.text=}")
                breakpoint()
                print(f"{err=}")
    # breakpoint()


@bigcomm.command("list-webhooks")
def list_webhooks():
    api = bigcommerce.get_app_client_for_store()
    webhooks_list_resp = api.Webhooks.all()
    print(f"list_webhooks(): {webhooks_list_resp=}")
    return webhooks_list_resp


@bigcomm.command("ensure-order-webhook")
def ensure_order_webhook(
    scope="store/order/*", destination_view="bigcommerce.order_webhook"
):
    api = bigcommerce.get_app_client_for_store()

    destination_url = url_for(destination_view, _external=True, _scheme="https")
    webhook_token = bigcommerce.generate_webhook_token(api=api)
    webhook_params = dict(
        scope=scope,
        destination=destination_url,
        is_active=True,
        events_history_enabled=True,
        headers=dict(
            authorization=f"bearer {webhook_token}",
        ),
    )
    logger.debug(
        f"add_webhooks(): {api.connection.store_hash=} {webhook_token[0:2]=}...{webhook_token[-2:]=}"
    )

    extant_webhooks = api.Webhooks.all()
    for extant_webhook in extant_webhooks:
        # breakpoint()
        # extant_webhook["headers"] = {
        #     k: f"...{v[-2:]}" for k, v in extant_webhook["headers"].items()
        # }
        logger.debug(f"{extant_webhook['id']=}")
        if (
            extant_webhook["scope"] == scope
            and extant_webhook["destination"] == destination_url
        ):
            print(
                f"Webhook already present ({extant_webhook['id']=}) performing updates now..."
            )
            webhooks_update_resp = extant_webhook.update(**webhook_params)
            webhooks_update_resp["headers"] = {
                k: f"...{v[-2:]}" for k, v in webhooks_update_resp["headers"].items()
            }
            print(f"add_webhooks(): {webhooks_update_resp=}")
            break
    else:
        webhooks_create_resp = api.Webhooks.create(**webhook_params)
        webhooks_create_resp["headers"] = {
            k: f"...{v[-2:]}" for k, v in webhooks_create_resp["headers"].items()
        }
        print(f"add_webhooks(): {webhooks_create_resp=}")

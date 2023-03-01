#!/usr/bin/env python
import logging

import click
from flask_security import SQLAlchemySessionUserDatastore
from sqlalchemy.exc import NoResultFound
from sqlalchemy.sql import func
from member_card.models.user import edit_user_name

from member_card.app import app
from member_card.db import db
from member_card.image import generate_card_image
from member_card.models import AnnualMembership, User
from member_card.models.membership_card import get_or_create_membership_card
from member_card.models.user import Role
from member_card.passes import gpay
from member_card.gcp import publish_message
from member_card.sendgrid import update_sendgrid_template
from member_card import worker
from member_card.minibc import Minibc, parse_subscriptions

logger = logging.getLogger(__name__)


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
def add_role_to_user(user_email, role_name):
    logger.debug(f"{user_email=} => {role_name=}")
    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)

    user = user_datastore.get_user(user_email)
    admin_role = user_datastore.find_or_create_role(
        name=role_name,
        description="Administrators allowed to connect Squarespace extensions, etc.",
    )
    db.session.add(admin_role)
    db.session.commit()
    logger.info(f"Adding {admin_role=} to user: {user=}")
    user_datastore.add_role_to_user(user=user, role=admin_role)
    logger.info(f"{admin_role=} successfully added for {user=}!")
    db.session.add(user)
    db.session.commit()


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

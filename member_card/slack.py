import json
import logging
from time import sleep

from codetiming import Timer
from flask import current_app
from slack_sdk import WebClient

from member_card.db import db, get_or_update
from member_card.models import SlackUser
from member_card.models.user import ensure_user

logger = logging.getLogger(__name__)


def get_web_client() -> WebClient:
    slack_bot_token = current_app.config["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_bot_token)
    return client


@Timer(name="slack_members_generator", logger=logger.debug)
def slack_members_generator(client: WebClient, chunk_size=100, polling_interval_secs=1):
    next_cursor = None
    while next_cursor != "":
        logger.debug(f"Sending users_lists request with: {next_cursor=}")
        response = client.users_list(
            limit=chunk_size,
            cursor=next_cursor,
        )
        response.validate()

        # cache_ts_epoch = datetime.fromtimestamp(response.data.get("cache_ts"))
        # cache_ts = cache_ts_epoch.strftime("%c")
        # logger.debug(f"{cache_ts=}")

        slack_members = response.data["members"]
        next_cursor = response.data["response_metadata"]["next_cursor"]
        logger.debug(f"Meta-response bits: [next_]next_cursor={next_cursor}")
        logger.debug(f"# slack users load thus far: {len(slack_members)=}")
        for slack_member in slack_members:
            logger.debug(f"yielding {slack_member=}...")
            yield slack_member

        logger.debug(f"Pausing for {polling_interval_secs=} before proceeding...")
        sleep(polling_interval_secs)


@Timer(name="upsert_slack_member", logger=logger.debug)
def upsert_slack_member(slack_member):
    profile_dict = slack_member["profile"]
    slack_member["profile"] = json.dumps(profile_dict)

    email = profile_dict.get("email")
    first_name = profile_dict.get("first_name")
    last_name = profile_dict.get("last_name")

    slack_member["slack_id"] = slack_member["id"]
    del slack_member["id"]

    if "email" not in slack_member:
        slack_member["email"] = email

    slack_user = get_or_update(
        session=db.session,
        model=SlackUser,
        filters=["slack_id"],
        kwargs=slack_member,
    )

    app_user = ensure_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    app_user_id = app_user.id
    if not slack_user.user_id:
        logger.debug(f"No user_id set for {slack_user=}! Setting to: {app_user_id=}")
        setattr(slack_user, "user_id", app_user_id)

    return slack_user


@Timer(name="slack_members_etl", logger=logger.debug)
def slack_members_etl(client: WebClient):
    slack_users = list()

    for slack_member in slack_members_generator(client):
        logger.debug(f"slack_members_etl(): {slack_member}")
        slack_user = upsert_slack_member(slack_member)
        slack_users.append(slack_user)
        db.session.add(slack_user)

        db.session.commit()

    logger.info(f"Total number of slack members processed: {len(slack_users)}")

    return slack_users


if __name__ == "__main__":
    import os

    slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_bot_token)
    response = client.users_list()

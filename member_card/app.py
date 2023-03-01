#!/usr/bin/env python
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    flash,
)
from flask_cdn import CDN
from flask_recaptcha import ReCaptcha
from flask_security import Security
from flask_security.core import current_user as current_login_user
from flask_security.decorators import login_required, roles_required
from flask_security.utils import logout_user
from social_flask.template_filters import backends
from social_flask.utils import load_strategy

from member_card import utils
from member_card.db import db
from member_card.exceptions import MemberCardException
from member_card.models import (
    AnnualMembership,
    MembershipCard,
    SquarespaceWebhook,
    User,
)
from member_card.models.membership_card import get_or_create_membership_card
from member_card.models.user import edit_user_name
from member_card.passes import get_apple_pass_from_card
from member_card.gcp import publish_message
from member_card.squarespace import (
    InvalidSquarespaceWebhookSignature,
    ensure_orders_webhook_subscription,
    generate_oauth_authorize_url,
    process_order_webhook_payload,
)

app = Flask(__name__)
logger = app.logger
logger.propagate = True

login_manager = utils.MembershipLoginManager()

security = Security()

recaptcha = ReCaptcha()

cdn = CDN()


@app.before_request
def global_user():
    # evaluate proxy value
    g.user = current_login_user._get_current_object()


@app.teardown_appcontext
def commit_on_success(error=None):
    if "sqlalchemy" not in app.extensions:
        # TODO: do this better
        return
    if error is None:
        db.session.commit()
    else:
        db.session.rollback()

    db.session.remove()


@app.context_processor
def inject_user():
    return {
        "user": getattr(g, "user", None),
    }


@app.template_filter()
def datetime_format(value, format="%x"):
    return value.strftime(format)


@app.context_processor
def load_common_context():
    # from member_card.db import get_membership_table_last_sync

    return utils.common_context(
        app.config["SOCIAL_AUTH_AUTHENTICATION_BACKENDS"],
        load_strategy(),
        getattr(g, "user", None),
        app.config.get("SOCIAL_AUTH_GOOGLE_PLUS_KEY"),
        # membership_last_sync=get_membership_table_last_sync(),
    )


app.context_processor(backends)
app.jinja_env.globals["url"] = utils.social_url_for


def active_membership_card_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not g.user.has_active_memberships:
            return redirect(
                url_for("no_active_membership_landing_page", **request.args)
            )

        membership_card = get_or_create_membership_card(g.user)

        return f(*args, membership_card=membership_card, **kwargs)

    return decorated_function


@app.errorhandler(MemberCardException)
def handle_bad_request(e):
    redirect_url = url_for("login")
    e.flash_em_if_you_got_em()
    return redirect(redirect_url)


@app.route("/")
@active_membership_card_required
def home(membership_card):
    return render_template(
        "member_card_and_history.html.j2",
        membership_card=membership_card,
        membership_orders=g.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


def generate_membership_stats():
    memberships = AnnualMembership.query.filter()
    total_num_memberships = memberships.count()

    active_memberships = AnnualMembership.query.filter(
        AnnualMembership.created_on >= (datetime.utcnow() - timedelta(days=365))
    )
    num_active_memberships = active_memberships.count()

    users = User.query.filter()

    membership_stats = {
        "Membership Orders (Total)": total_num_memberships,
        "Membership Orders (Active)": num_active_memberships,
        "Membership Orders (Expired)": total_num_memberships - num_active_memberships,
        "Users (Total)": users.count(),
    }
    logger.debug(f"{membership_stats=}")
    return membership_stats


def generate_user_stats():
    user_stats = {
        "Newest User": db.session.query(AnnualMembership)
        .order_by(AnnualMembership.created_on.desc())
        .first()
        .user,
        "Oldest User": db.session.query(AnnualMembership)
        .order_by(AnnualMembership.created_on.asc())
        .first()
        .user,
    }
    return user_stats


@app.route("/admin-dashboard")
@login_required
@roles_required("admin")
def admin_dashboard():
    return render_template(
        "admin_dashboard.html.j2",
        membership_stats=generate_membership_stats(),
        user_stats=generate_user_stats(),
    )


@app.route("/no-active-membership-found")
@login_required
def no_active_membership_landing_page():
    return render_template(
        "no_membership_landing_page.html.j2",
        user=g.user,
        membership_orders=g.user.annual_memberships,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


@app.route("/edit-user-name", methods=["POST"])
@login_required
def edit_user_name_request():
    log_extra = dict(form=request.form)
    new_first_name = request.form["newFirstName"]
    new_last_name = request.form["newLastName"]
    logger.debug(
        f"edit_user_name_request(): {new_first_name=} {new_last_name=}", extra=log_extra
    )
    edit_user_name(
        user=g.user,
        new_first_name=new_first_name,
        new_last_name=new_last_name,
    )
    flash(utils.get_message_str("edit_user_name_success"), "info")
    return redirect(f"{url_for('home')}")


@app.route("/email-distribution-request", methods=["POST"])
def email_distribution_request():
    from email_validator import EmailNotValidError, validate_email

    log_extra = dict(form=request.form)

    # First prerequisite: verified recaptcha stuff:
    if not recaptcha.verify():
        flash(utils.get_message_str("captcha_not_verified"), "form-error")
        logger.error(
            "Unable to verify recaptcha, redirecting to login", extra=log_extra
        )
        return redirect(url_for("login"))

    email_distribution_recipient = request.form.get("emailDistributionRecipient")
    if email_distribution_recipient is None:
        flash(
            utils.get_message_str("missing_email_distribution_recipient"), "form-error"
        )
        logger.error(
            "No email recipient email address provided ({email_distribution_recipient=})! redirecting to login",
            extra=log_extra,
        )
        return redirect(url_for("login"))

    log_extra.update(dict(email_distribution_recipient=email_distribution_recipient))

    # Second prerequisite: we can actually send to this address
    try:
        # Validate.
        valid = validate_email(email_distribution_recipient)

        # Update with the normalized form.
        email_distribution_recipient = valid.email
        log_extra.update(
            dict(email_distribution_recipient=email_distribution_recipient)
        )
    except EmailNotValidError as err:
        log_extra.update(dict(err=err))
        # email is not valid, exception message is human-readable
        email_form_error_message = str(err)
        flash(email_form_error_message, "form-error")
        logger.error(
            "Unable to validate email, redirecting to login",
            extra=dict(form=request.form),
        )
        return redirect(url_for("login"))

    topic_id = app.config["GCLOUD_PUBSUB_TOPIC_ID"]
    logger.info(
        f"publishing email distribution request to pubsub {topic_id=}", extra=log_extra
    )
    publish_message(
        project_id=app.config["GCLOUD_PROJECT"],
        topic_id=topic_id,
        message_data=dict(
            type="email_distribution_request",
            email_distribution_recipient=email_distribution_recipient,
            remote_addr=request.remote_addr,
            submitted_on=datetime.utcnow().isoformat(),
        ),
    )

    return render_template(
        "email_request_landing_page.html.j2",
        submitted_email=email_distribution_recipient,
        submission_response_msg="Request received",
        redirect_home_delay_seconds="45",
    )


@app.route("/passes/google-pay")
@active_membership_card_required
def passes_google_pay(membership_card):
    return redirect(membership_card.google_pass_save_url)


@app.route("/passes/apple-pay")
@active_membership_card_required
def passes_apple_pay(membership_card):
    attachment_filename = f"lv_apple_pass-{g.user.last_name.lower()}.pkpass"
    pkpass_out_path = get_apple_pass_from_card(
        membership_card=membership_card,
    )
    return send_file(
        pkpass_out_path,
        attachment_filename=attachment_filename,
        mimetype="application/vnd.apple.pkpass",
        as_attachment=True,
    )


@app.route("/squarespace/oauth/login")
@login_required
@roles_required("admin")
def squarespace_oauth_login():
    authorize_url = generate_oauth_authorize_url()
    return redirect(authorize_url)


@app.route("/squarespace/oauth/connect")
@login_required
@roles_required("admin")
def squarespace_oauth_callback():
    try:
        webhook_subscriptions = ensure_orders_webhook_subscription(
            code=request.args.get("code"),
            endpoint_url=app.config["SQUARESPACE_ORDER_WEBHOOK_ENDPOINT"],
        )
        logger.debug(
            "Webhook ensurenment complete! :D",
            extra=dict(webhook_subscriptions=webhook_subscriptions),
        )

    except Exception as err:
        logger.error(err)
        return redirect(
            f"{url_for('squarespace_extension_details')}?formErrorMessage={str(err)}"
        )

    return redirect(url_for("squarespace_extension_details"))


@app.route("/squarespace/extension-details")
@login_required
@roles_required("admin")
def squarespace_extension_details():
    webhooks = SquarespaceWebhook.query.order_by(
        SquarespaceWebhook.created_on.desc()
    ).all()
    logger.debug(f"Webhook entries in the database: {webhooks=}")
    return render_template(
        "squarespace_extension_details.html.j2",
        webhooks=webhooks,
    )


@app.route("/squarespace/order-webhook", methods=["POST"])
def squarespace_order_webhook():
    try:
        process_order_webhook_payload()
    except NotImplementedError as err:
        return str(err), 422
    except InvalidSquarespaceWebhookSignature as err:
        return str(err), 401
    return "thanks buds!", 200


@app.route("/verify-pass/<serial_number>")
@login_required
# Note: get_or_create_membership_card() has this route hard-coded in it
# TODO: ^ make that not the case
def verify_pass(serial_number):
    signature = request.args.get("signature")
    if not signature:
        raise MemberCardException(
            form_error_message=utils.get_message_str("verify_pass_invalid_signature"),
        )

    signature_verified = utils.verify(signature=signature, data=serial_number)
    if not signature_verified:
        raise MemberCardException(
            form_error_message=utils.get_message_str("verify_pass_invalid_signature"),
        )

    verified_card = (
        db.session.query(MembershipCard).filter_by(serial_number=serial_number).one()
    )
    logger.debug(f"{verified_card=}")
    validation_msg = "CARD VALIDATED!"
    if verified_card.is_voided:
        validation_msg = "CARD EXPIRED (but valid)!"
    return render_template(
        "apple_pass_validation.html.j2",
        validating_user=g.user,
        validation_msg=validation_msg,
        verified_card=verified_card,
        membership_table_keys=list(AnnualMembership().to_dict().keys()),
    )


@app.route("/login")
def login():
    """Logout view"""
    return render_template(
        "login.html.j2",
        recaptcha_site_key=app.config["RECAPTCHA_SITE_KEY"],
    )


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "privacy_policy.html.j2",
    )


@app.route("/about")
def about():
    return render_template(
        "about.html.j2",
    )

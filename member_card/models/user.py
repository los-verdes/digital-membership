from datetime import timedelta
import logging
from member_card.db import db, get_or_create
from sqlalchemy.orm import relationship, backref
from flask_security import UserMixin, RoleMixin


logger = logging.getLogger(__name__)


def edit_user_name(user, new_first_name, new_last_name):
    logger.info(
        f"Update name for {user} from {user.fullname} to: {new_first_name} {new_last_name}"
    )
    setattr(user, "fullname", " ".join([new_first_name, new_last_name]))
    setattr(user, "first_name", new_first_name)
    setattr(user, "last_name", new_last_name)
    db.session.add(user)
    db.session.commit()
    logger.debug(f"post-commit: {user=}")
    return user


def ensure_user(
    email,
    first_name=None,
    last_name=None,
    username=None,
    password=None,
    bigcommerce_id=None,
):
    user = get_or_create(
        session=db.session,
        model=User,
        email=email,
    )

    if not user.fullname and first_name is not None and last_name is not None:
        member_name = f"{first_name} {last_name}"
        logger.debug(f"No name set yet on {user=}, updating to: {member_name}")
        user.fullname = member_name
        user.first_name = first_name
        user.last_name = last_name

    if user.first_name != first_name:
        logger.warning(
            f"{user.first_name=} does not match {first_name} for some reason..."
        )
    if user.last_name != last_name:
        logger.warning(
            f"{user.last_name=} does not match {last_name} for some reason..."
        )

    if username is not None:
        logger.debug(f"Setting new username for {user=}: {username}")
        setattr(user, "username", username)

    if password is not None:
        logger.debug(f"Setting new password for {user=}")
        setattr(user, "password", password)

    if bigcommerce_id is not None:
        logger.debug(f"Setting bigcommerce_id for {user=} => {bigcommerce_id=}")
        setattr(user, "bigcommerce_id", bigcommerce_id)

    db.session.add(user)
    db.session.commit()
    return user


roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer(), db.ForeignKey("users.id")),
    db.Column("role_id", db.Integer(), db.ForeignKey("role.id")),
)


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return f"<Role {self.id} {self.name=} {self.description=} >"

    def __repr__(self):
        return f"<Role {self.id} {self.name=} {self.description=} >"


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200))
    email = db.Column(db.String(200), unique=True)
    fullname = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)
    annual_memberships = relationship("AnnualMembership", back_populates="user")
    membership_cards = relationship("MembershipCard", back_populates="user")
    store_users = relationship("StoreUser", backref="user")
    bigcommerce_id = db.Column(db.Integer, nullable=True)
    roles = relationship(
        "Role",
        secondary="roles_users",
        backref=backref("users", lazy="dynamic", cascade="save-update"),
        cascade="save-update",
    )

    def to_dict(self):
        return dict(
            id=self.id,
            # TODO: figure out why we're not getting usernames set...
            # username=self.username,
            email=self.email,
            fullname=self.fullname,
            first_name=self.first_name,
            last_name=self.last_name,
            active=self.active,
        )

    def is_active(self):
        return self.active

    def __str__(self):
        return f"<User {self.id} {self.fullname=} ({self.first_name=} {self.last_name=}) {self.email=} {self.active=} >"

    @property
    def has_active_memberships(self):
        if not self.annual_memberships:
            return False
        return any(m.is_active for m in self.annual_memberships)

    def has_memberships(self):
        return len(self.annual_memberships) > 0

    @property
    def latest_membership_card(self):
        if not self.membership_cards:
            return None
        return sorted(self.membership_cards, key=lambda x: x.time_created)[-1]

    @property
    def oldest_membership(self):
        if not self.annual_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[0]

    @property
    def newest_membership(self):
        if not self.annual_memberships:
            return None
        return sorted(self.annual_memberships, key=lambda x: x.created_on)[-1]

    @property
    def member_since(self):
        if not self.oldest_membership:
            return None
        return self.oldest_membership.created_on

    @property
    def membership_expiry(self):
        if not self.newest_membership:
            return None
        return self.newest_membership.created_on + timedelta(days=365)

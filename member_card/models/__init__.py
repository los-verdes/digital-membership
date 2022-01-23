# from social_flask_peewee import models
# from flask_sqlalchemy import SQLAlchemy
from member_card.models.user import User
from member_card.models.table_metadata import TableMetadata
from member_card.models.annual_membership import AnnualMembership
from social_flask_sqlalchemy import models

assert AnnualMembership
assert User
assert TableMetadata
assert models
# db = SQLAlchemy()

# def get_db():
#   return db

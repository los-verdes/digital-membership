from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base

from flask_login import UserMixin

from member_card.utils import get_db_session


Base = declarative_base()
Base.query = get_db_session().query_property()
# Base.query = db_session.query_property()


class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(200))
    email = Column(String(200))
    fullname = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    active = Column(Boolean, default=True)

    # def get_id(self):

    def is_active(self):
        return self.active

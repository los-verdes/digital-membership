from flask_login import UserMixin
from member_card.db import Model
from sqlalchemy import Boolean, Column, Integer, String


class User(Model, UserMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(200))
    email = Column(String(200))
    fullname = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    active = Column(Boolean, default=True)

    def is_active(self):
        return self.active

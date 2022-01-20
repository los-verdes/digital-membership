#!/usr/bin/env python
# from flask_script import Server, Manager, Shell
from member_card.app import app
# from example import app, db_session, engine


# manager = Manager(app)
# manager.add_command('runserver', Server())
# manager.add_command('shell', Shell(make_context=lambda: {
#     'app': app,
#     # 'db_session': db_session
# }))


# @manager.command -> this could maybe replace populate_db.py?
# def syncdb():
#     from member_card.models.user import User
#     from social_flask_sqlalchemy import models
#     user.Base.metadata.create_all(engine)
#     models.PSABase.metadata.create_all(engine)

if __name__ == '__main__':
    # manager.run()
    from member_card.models.user import User
    from social_flask_peewee.models import FlaskStorage
    models = [
        User,
        FlaskStorage.user,
        FlaskStorage.nonce,
        FlaskStorage.association,
        FlaskStorage.code,
        FlaskStorage.partial
    ]
    for model in models:
        model.create_table(True)
    app.run(
        host="0.0.0.0",
        debug=True,
        ssl_context='adhoc',
    )

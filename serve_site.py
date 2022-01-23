#!/usr/bin/env python
# from member_card import app, engine
# # from flask import Flask

# # member_card = Flask(__name__)


# if __name__ == "__main__":
#     import argparse
#     import logging

#     import logzero

#     parser = argparse.ArgumentParser()
#     parser.add_argument(
#         "-q",
#         "--quiet",
#         help="modify output verbosity",
#         action="store_true",
#     )
#     parser.add_argument(
#         "-D",
#         "--no-dev",
#         help="toggles off flask debug & 'adhoc' ssl modes",
#         action="store_false",
#     )
#     args = parser.parse_args()

#     if args.quiet:
#         logzero.loglevel(logging.INFO)
#     # manager.run()
#     # from member_card.models.user import User
#     # from social_flask_peewee.models import FlaskStorage

#     # models = [
#     #     User,
#     #     FlaskStorage.user,
#     #     FlaskStorage.nonce,
#     #     FlaskStorage.association,
#     #     FlaskStorage.code,
#     #     FlaskStorage.partial,
#     # ]
#     # for model in models:
#     #     model.create_table(True)

#     app_run_kwargs = dict()
#     if not args.no_dev:
#         app_run_kwargs["debug"] = True
#         app_run_kwargs["ssl_context"] = "adhoc"

#     member_card.run(
#         host="0.0.0.0",
#         **app_run_kwargs,
#     )

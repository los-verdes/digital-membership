# class TestSquarespaceOauth:
#     def test_squarespace_oauth_callback_error_in_args(
#         self,
#         admin_client: "FlaskClient",
#     ):
#         response = admin_client.get(
#             "/squarespace/oauth/connect?error=literally-anything-for-this-param",
#             follow_redirects=True,
#         )
#         assert response.history[0].status_code == 302
#         assert response.history[0].location.startswith(
#             "http://localhost/squarespace/extension-details?"
#         )
#         assert_form_error_message(
#             response=response,
#             expected_msg=utils.get_message_str("squarespace_oauth_connect_error"),
#         )

#     def test_squarespace_oauth_callback_missing_state(
#         self,
#         admin_client: "FlaskClient",
#     ):
#         response = admin_client.get(
#             "/squarespace/oauth/connect",
#             follow_redirects=True,
#         )
#         assert response.history[0].status_code == 302
#         assert response.history[0].location.startswith(
#             "http://localhost/squarespace/extension-details?"
#         )
#         assert_form_error_message(
#             response=response,
#             expected_msg=utils.get_message_str(
#                 "squarespace_oauth_connect_missing_state"
#             ),
#         )

#     def test_squarespace_oauth_callback_state_mismatch(
#         self,
#         admin_client: "FlaskClient",
#     ):

#         with admin_client.session_transaction() as session:
#             session["state"] = "test-state..."
#         response = admin_client.get(
#             f"/squarespace/oauth/connect?state={session['state']}",
#             follow_redirects=True,
#         )
#         assert response.history[0].status_code == 302
#         assert response.history[0].location.startswith(
#             "http://localhost/squarespace/extension-details?"
#         )
#         assert_form_error_message(
#             response=response,
#             expected_msg=utils.get_message_str("squarespace_oauth_state_mismatch"),
#         )

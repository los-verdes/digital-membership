def set_current_user(login_manager, user):
    """Set up so that when request is received,
    the token will cause 'user' to be made the current_user
    """

    def token_cb(request):
        raise Exception("hiya")
        if request.headers.get("Authentication-Token") == "token":
            return user
        return login_manager.anonymous_user()

    login_manager.request_loader(token_cb)


def create_fake_user(
    user_cls, email="los.verdes.tester@gmail.com", userid=1, roles=None
):
    """Create fake user optionally with roles"""
    user = user_cls()
    user.email = email
    user.id = userid
    user.password = "mypassword"
    user.active = True
    if roles:
        if isinstance(roles, list):
            user.roles = roles
        else:
            user.roles = [roles]
    return user


def create_fake_role(role_cls, name):
    return role_cls(name=name)

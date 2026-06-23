"""
auth.py
Handles password hashing and login verification.
"""

import bcrypt
import database as db


def hash_password(password):

    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")



def verify_password(password,hashed):

    try:

        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8")
        )

    except:

        return False



def login(email,password):

    user=db.get_user_by_email(email)


    if user is None:

        return None


    if verify_password(
        password,
        user["password_hash"]
    ):

        return dict(user)


    return None



def signup(
    company_name,
    email,
    password,
    full_name,
    role
):


    existing=db.get_user_by_email(email)


    if existing:

        return False,"An account with this email already exists."



    if len(password)<6:

        return False,"Password must be at least 6 characters."



    if not company_name or not company_name.strip():

        return False,"Company name is required."

    VALID_ROLES = ("reviewer", "manager", "finance/admin")
    if role not in VALID_ROLES:
        return False, f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}."

    db.create_user(

        company_name,

        email,

        hash_password(password),

        full_name,

        role

    )

    return True,"Account created. You can now login."

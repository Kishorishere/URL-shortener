from rest_framework.exceptions import APIException
from rest_framework import status


class InvalidCredentialsError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class UserAlreadyExistsError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A user with this email already exists."
    default_code = "user_exists"


class EmailNotVerifiedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Please verify your email address before signing in."
    default_code = "email_not_verified"

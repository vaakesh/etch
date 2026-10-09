class InvalidTokenError(Exception):
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)


class InvalidRefreshTokenError(Exception):
    def __init__(self, message: str = "Invalid refresh token"):
        super().__init__(message)


class InvalidTokenTypeError(InvalidTokenError):
    def __init__(self, message: str = "Invalid token type"):
        super().__init__(message)


class RefreshTokenNotFoundError(InvalidTokenError):
    def __init__(self, message: str = "Refresh token not found"):
        super().__init__(message)


class AccessTokenNotFoundError(InvalidTokenError):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message)

class InvalidLoginCredentials(Exception):
    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(message)


class CaptchaError(Exception):
    def __init__(self, message: str = "Captcha verification failed"):
        super().__init__(message)
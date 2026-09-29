class ApiError(Exception):
    """
    Base Exception for Api Errors
    """

    def __init__(self, message: str, retcode: int = None):
        self.retcode = retcode
        super().__init__(message)


class AuthkeyError(ApiError):
    """
    Error for invalid authkeys
    """


class AuthkeyTimeoutError(ApiError):
    """
    Error for timeouted authkeys
    """


class ApiConnectionError(ApiError):
    """
    Error for API connection errors
    """


class GachaTypeError(Exception):
    """
    Error for invalid gacha types
    """

    def __init__(self, message: str):
        super().__init__(message)

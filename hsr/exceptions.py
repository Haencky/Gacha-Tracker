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


class ApiConnectionError(ApiError):
    """
    Error for API connection errors
    """

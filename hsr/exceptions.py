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


class ItemCatalogError(Exception):
    """
    Base class for item catalog errors
    """

    def __init__(self, message: str):
        super().__init__(message)


class ItemCatalogUnknownTypeError(ItemCatalogError):
    """
    Error if "characters" and "lightcones" got renamed
    """


class ItemCatalogItemDoesNotExistError(ItemCatalogError):
    """
    Error if item_id does not exists in response json
    """


class FileError(Exception):
    """
    Error for unreadable files
    """

    def __init__(self, message: str, type: str = "legacy"):
        self.type = type
        super().__init__(message)


class LegacyFileError(FileError):
    """
    Error if the legacy database file can not be read
    """

    def __init__(self, message, type="legacy"):
        super().__init__(message, "legacy")


class UIDError(Exception):
    """
    Error if uid cant be pased
    """

    def __init__(self, message):
        super().__init__(message)


class PetError(ApiError):
    """
    Base class for pet api
    """

    def __init__(self, message, retcode: int = None):
        self.retcode = retcode
        super().__init__(message)


class LanguageError(ApiError):
    def __init__(self, message):
        self.retcode = 108
        super().__init__(message)

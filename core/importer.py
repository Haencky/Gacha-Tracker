from abc import ABC, abstractmethod


class AbstractPullRecord(ABC):
    """
    Abstract base class for custom pull record classes

    Attributes:
        time(str): timestamp
        id(str): pull identifier
        uid(str): user identifier
        gacha_type(str): gacha type identifer
    """

    time: str
    id: str
    uid: str
    gacha_type: str


class AbstractParser(ABC):
    """
    Abstract base class for custom parser classes
    """

    @abstractmethod
    def fetch(self) -> list[AbstractPullRecord]:
        """
        Abstract function for any type of import

        Returns:
            records(list[AbstractPullRecord])
        """


class AbstractPullWriter(ABC):
    """
    Abstract base class for custom writer classes
    """

    @abstractmethod
    def write(self, record: AbstractPullRecord):
        """
        Writes given pull record to database
        Calls support functions if needed

        Args:
            record(AbstractPullRecord): pull to be written to the DB
        """

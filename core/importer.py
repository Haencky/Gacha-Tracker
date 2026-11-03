from abc import ABC, abstractmethod
from dataclasses import dataclass


class AbstractPullRecord(ABC):
    """
    Abstract base class for custom pull record classes

    Attributes:
        time(str): timestamp
        id(str): pull identifier
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
    def write(self, records: list[AbstractPullRecord]) -> ImportResult:
        """
        Writes given pull records to database
        Calls support functions if needed

        Args:
            record(list): pulls to be written to the DB
        """


@dataclass
class ImportResult:
    created: int
    skipped: int
    new_items: int
    unknown_items: set[str]

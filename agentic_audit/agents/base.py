from abc import ABC, abstractmethod
from typing import Any, Dict


class Agent(ABC):
    """Base class for all agents.

    Agents implement `run(records)` and return a dict with findings.
    """

    @abstractmethod
    def run(self, records: Any) -> Dict:
        raise NotImplementedError

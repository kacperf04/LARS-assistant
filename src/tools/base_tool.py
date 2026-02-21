from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """Base class for all tools."""
    def __init__(self, name: str) -> None:
        logger.info(f"Initializing tool [{name}]...")
        self.name = name


    @abstractmethod
    def run(self, query: str) -> str:
        """Runs the tool on the given query"""
        pass
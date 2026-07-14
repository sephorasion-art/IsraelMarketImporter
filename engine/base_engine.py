from abc import ABC, abstractmethod

from engine.models import EnginePayload, RuntimeOptions


class BaseEngine(ABC):

    @abstractmethod
    def scrape(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
        raise NotImplementedError

    def get_html(self, url: str, options: RuntimeOptions | None = None) -> str:
        return self.scrape(url, options).html
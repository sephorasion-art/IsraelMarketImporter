from abc import ABC, abstractmethod


class BaseEngine(ABC):

    @abstractmethod
    def scrape(self, url):
        pass
import requests
from bs4 import BeautifulSoup

from engine.base_engine import BaseEngine


class HtmlEngine(BaseEngine):

    def scrape(self, url):

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers)

        response.raise_for_status()

        return BeautifulSoup(response.text, "lxml")
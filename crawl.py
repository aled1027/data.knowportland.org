import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortlandMinutesScraper:

    def __init__(self, outdir: str):
        self.base_url = "https://efiles.portlandoregon.gov"

        # We have ?pageSize and ?start for pagination
        self.start_url = (
            "https://efiles.portlandoregon.gov/record?"
            "q=recContainer:17141116&sortBy=recCreatedOn&pageSize=1000&start=0"
        )

        self.outdir = outdir
        os.makedirs(self.outdir, exist_ok=True)

    def _fetch_html(self, url: str) -> str:
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def _save_file(self, pdf_url: str, filename: str) -> None:
        """Used for saving a pdf or another file type"""
        response = requests.get(pdf_url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)

    def _extract_pdf_url(self, soup) -> str | None:
        try:
            iframe_link = soup.find_all("iframe")[1]["src"]
        except (IndexError, KeyError):
            logger.warning(f"No valid iframe found")
            return None

        iframe_url = urljoin(self.base_url, iframe_link)
        iframe_response = requests.get(iframe_url)
        iframe_response.raise_for_status()

        iframe_soup = BeautifulSoup(iframe_response.text, "html.parser")
        pdf_links = [
            a
            for a in iframe_soup.find_all("a", title="Download File")
            if a.get_text(strip=True).lower() == "pdf" and "href" in a.attrs
        ]

        if not pdf_links:
            logger.warning(f"No PDF link found on {iframe_url}")
            return None

        return urljoin(self.base_url, pdf_links[0]["href"])

    def scrape_all(self):
        # The start url is basically the list of meetings (paginated)
        # Pagination isn't handled yet
        html = self._fetch_html(self.start_url)
        soup = BeautifulSoup(html, "html.parser")

        def is_good_tag(tag):
            # Check if the tag is an <a> tag with "href" and contains "minutes"
            return (
                tag.name == "a"
                and "href" in tag.attrs
                and "minutes" in tag.get_text(strip=True).lower()
            )

        a_tags = soup.find_all("a", href=True)
        a_tags = [a for a in a_tags if is_good_tag(a)]
        print(f"Found {len(a_tags)} meeting links.")

        data = []
        for i, a_tag in enumerate(a_tags):
            meeting_page_url = urljoin(self.base_url, a_tag["href"]).rstrip("/")
            meeting_id = meeting_page_url.rstrip("/").split("/")[-1]
            logger.info("Processing %s / %s: %s", i, len(a_tags), meeting_page_url)

            meeting_soup = BeautifulSoup(
                self._fetch_html(meeting_page_url), "html.parser"
            )
            title = meeting_soup.find("h2").get_text(strip=True)
            logger.info("Processing meeting: %s", title)

            pdf_url = self._extract_pdf_url(meeting_soup)
            if not pdf_url:
                continue

            file_id = pdf_url.rstrip("/").split("/")[-3]
            filename = os.path.join(self.outdir, f"{file_id}.pdf")
            self._save_file(pdf_url, filename)

            metadata = {
                "file_id": file_id,
                "meeting_id": meeting_id,
                "pdf_url": pdf_url,
                "meeting_page_url": meeting_page_url,
                "filename": filename,
                "title": title,
            }
            data.append(metadata)
            time.sleep(1)

        # Write data to a file
        with open(os.path.join(self.outdir, "metadata.json"), "w") as f:
            json.dump(data, f, indent=4)


if __name__ == "__main__":
    outdir = "data/portland_minutes_pdfs"
    scraper = PortlandMinutesScraper(outdir)
    scraper.scrape_all()

"""
Crawler implementation.
"""

# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable, unused-argument
import datetime
import json
import pathlib
import re
import shutil
import urllib.parse

import requests
from bs4 import BeautifulSoup, Tag
from requests.exceptions import RequestException

from core_utils.article.article import Article
from core_utils.article.io import to_raw, to_meta
from core_utils.config_dto import ConfigDTO
from core_utils.constants import CRAWLER_CONFIG_PATH

class IncorrectSeedURLError(Exception):
    """Raised when seed URL does not match required pattern."""

class NumberOfArticlesOutOfRangeError(Exception):
    """Raised when total number of articles is out of range 1 - 150."""

class IncorrectNumberOfArticlesError(Exception):
    """Raised when total number of articles is not integer or less than 0."""

class IncorrectHeadersError(Exception):
    """Raised when headers are not a dictionary."""

class IncorrectEncodingError(Exception):
    """Raised when encoding is not a string."""

class IncorrectTimeoutError(Exception):
    """Raised when timeout is not a positive integer less than 60."""

class IncorrectVerifyError(Exception):
    """Raised when verify certificate or headless mode is not a boolean."""

class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self._config_dto: ConfigDTO | None = None
        self._validate_config_content()

    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as file:
            config_data = json.load(file)

        return ConfigDTO(
            seed_urls=config_data.get('seed_urls', []),
            headers=config_data.get('headers', {}),
            total_articles_to_find_and_parse=config_data.get('total_articles_to_find_and_parse', 0),
            encoding=config_data.get('encoding', 'utf-8'),
            timeout=config_data.get('timeout', 10),
            should_verify_certificate=config_data.get('should_verify_certificate', True),
            headless_mode=config_data.get('headless_mode', True)
        )

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        self._config_dto = self._extract_config_content()
        dto = self._config_dto

        if not isinstance(dto.seed_urls, list):
            raise IncorrectSeedURLError("seed_urls must be a list")
        if not dto.seed_urls:
            raise IncorrectSeedURLError("seed_urls cannot be empty")
        url_pattern = re.compile(r'^https?://(www\.)?')
        for url in dto.seed_urls:
            if not url_pattern.match(url):
                raise IncorrectSeedURLError(f"Invalid seed URL: {url}")

        total = dto.total_articles

        if not isinstance(total, int):
            raise IncorrectNumberOfArticlesError("total_articles must be an integer")
        if total < 0:
            raise IncorrectNumberOfArticlesError("total_articles cannot be negative")
        if total < 1 or total > 150:
            raise NumberOfArticlesOutOfRangeError("total_articles must be in range 1..150")
        if not isinstance(dto.headers, dict):
            raise IncorrectHeadersError("headers must be a dictionary")
        if not isinstance(dto.encoding, str):
            raise IncorrectEncodingError("encoding must be a string")
        if not isinstance(dto.timeout, int):
            raise IncorrectTimeoutError("timeout must be an integer")
        if dto.timeout <= 0 or dto.timeout > 60:
            raise IncorrectTimeoutError("timeout must be in range 1..60")
        if not isinstance(dto.should_verify_certificate, bool):
            raise IncorrectVerifyError("should_verify_certificate must be boolean")
        if not isinstance(dto.headless_mode, bool):
            raise IncorrectVerifyError("headless_mode must be boolean")

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        if self._config_dto:
            return self._config_dto.seed_urls
        return []

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        if self._config_dto:
            return self._config_dto.total_articles
        return 0

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        if self._config_dto:
            return self._config_dto.headers
        return {}

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        if self._config_dto:
            return self._config_dto.encoding
        return 'utf-8'

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        if self._config_dto:
            return self._config_dto.timeout
        return 10

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        if self._config_dto:
            return self._config_dto.should_verify_certificate
        return True

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        if self._config_dto:
            return self._config_dto.headless_mode
        return True

def make_request(url: str, config: Config) -> requests.Response | None:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    if url.startswith('#'):
        return None
    try:
        headers = config.get_headers()
        if not headers:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(
            url,
            headers=config.get_headers(),
            timeout=config.get_timeout(),
            verify=config.get_verify_certificate()
        )
        response.encoding = config.get_encoding()
        return response
    except RequestException:
        return None

class Crawler:
    """
    Crawler implementation.
    """

    #: Url pattern
    url_pattern: re.Pattern | str

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        self.config = config
        self.urls: list[str] = []

    def _extract_url(self, link_tag: Tag, base_url: str) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.Tag): Tag instance

        Returns:
            str: Url from HTML
        """
        href = link_tag.get('href')
        if not href or not isinstance(href, str):
            return ""
        full_url = urllib.parse.urljoin(base_url, href)
        return full_url

    def find_articles(self) -> None:
        """
        Find articles.
        """
        needed = self.config.get_num_articles()
        for seed in self.config.get_seed_urls():
            if len(self.urls) >= needed:
                break
            response = make_request(seed, self.config)
            if not response or response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                full_url = self._extract_url(link, seed)
                if full_url and full_url not in self.urls:
                    self.urls.append(full_url)
                    if len(self.urls) >= needed:
                        break

    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.config.get_seed_urls()

# 10

class CrawlerRecursive(Crawler):
    """
    Recursive implementation.

    Get one URL of the title page and find requested number of articles recursively.
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the CrawlerRecursive class.

        Args:
            config (Config): Configuration
        """
        super().__init__(config)
        seed_urls = self.config.get_seed_urls()
        if not seed_urls:
            raise IncorrectSeedURLError("No seed URLs provided for recursive crawler")
        self.start_url = seed_urls[0]
        self.num_articles = self.config.get_num_articles()
        self.url_pattern = re.compile(r"/\d{4}/\d{2}/\d{2}/")
        self._visited: set[str] = set()

    def _crawl(self, url: str) -> None:
        """
        Recursively crawl a single URL to collect article links.

        Args:
            url (str): URL to crawl
        """
        if len(self.urls) >= self.num_articles:
            return
        if url in self._visited:
            return
        self._visited.add(url)
        response = make_request(url, self.config)
        if not response or response.status_code != 200:
            return
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            full_url = self._extract_url(link, url)
            if not full_url:
                continue
            if self.url_pattern.search(full_url) and full_url not in self.urls:
                self.urls.append(full_url)
                if len(self.urls) >= self.num_articles:
                    return
            if len(self.urls) < self.num_articles:
                self._crawl(full_url)
                if len(self.urls) >= self.num_articles:
                    return

    def find_articles(self) -> None:
        """
        Find number of article urls requested.
        """
        if not self.start_url:
            return
        self._crawl(self.start_url)

# 4, 6, 8, 10

class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(full_url, article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        paragraphs = article_soup.find_all('p')
        text = ' '.join(p.get_text(strip=True) for p in paragraphs)
        self.article.text = text

    def _extract_authors(self, author_value: str) -> list[str]:
        """
        Extract authors from string, handling multiple authors separated by commas.

        Args:
            author_value (str): Raw author string

        Returns:
            list[str]: List of cleaned author names
        """
        if not author_value:
            return ["NOT FOUND"]
        authors = [a.strip() for a in author_value.split(',') if a.strip()]
        return authors if authors else ["NOT FOUND"]

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        title_tag = article_soup.find('title')
        if title_tag:
            self.article.title = title_tag.get_text(strip=True)

        author_tag = article_soup.find('meta', {'name': 'author'})
        if author_tag and author_tag.get('content'):
            self.article.author = [author_tag['content']]
        else:
            self.article.author = ["NOT FOUND"]
        date_tag = (article_soup.find('meta', {'name': 'date'}) or
                    article_soup.find('meta', {'property': 'article:published_time'}) or
                    article_soup.find('time'))
        if date_tag:
            date_str = date_tag.get('content') or date_tag.get('datetime') or date_tag.get_text()
            if date_str and isinstance(date_str, str):
                parsed_date = self.unify_date_format(date_str)
                if parsed_date:
                    self.article.date = parsed_date

        topics = []
        topic_tags = article_soup.find_all('meta', {'name': 'news_keywords'})
        for tag in topic_tags:
            if tag.get('content'):
                topics.extend(tag['content'].split(','))
        keywords_tag = article_soup.find('meta', {'name': 'keywords'})
        if keywords_tag and keywords_tag.get('content'):
            topics.extend(keywords_tag['content'].split(','))
        if topics:
            self.article.topics = list(dict.fromkeys(topics))[:5]
        else:
            self.article.topics = []

    def _parse_russian_date(self, date_str: str) -> datetime.datetime | None:
        """
        Parse Russian date formats (e.g., "26 января 2021").

        Args:
            date_str (str): Date string in Russian

        Returns:
            datetime.datetime | None: Parsed date or None
        """
        russian_months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }

        patterns = [
            r'(\d{1,2})\s+([а-я]+)\s+(\d{4})',
            r'(\d{1,2})\s+([а-я]+)\s+(\d{4}),\s+(\d{2}):(\d{2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, date_str.lower())
            if match:
                day = int(match.group(1))
                month_name = match.group(2)
                year = int(match.group(3))

                if month_name in russian_months:
                    month = russian_months[month_name]
                    if len(match.groups()) >= 5:
                        hour = int(match.group(4))
                        minute = int(match.group(5))
                        return datetime.datetime(year, month, day, hour, minute)
                    return datetime.datetime(year, month, day)

        return None

    def unify_date_format(self, date_str: str) -> datetime.datetime | None:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        russian_date = self._parse_russian_date(date_str)
        if russian_date:
            return russian_date

        formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%B %d, %Y',
            '%d %B %Y',
            '%d.%m.%Y',
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(date_str[:len(fmt)], fmt)
            except ValueError:
                continue

        return None

    def parse(self) -> Article | None:
        """
        Parse each article.

        Returns:
            Article | bool: Article instance, False in case of request error
        """
        response = make_request(self.full_url, self.config)
        if not response or response.status_code != 200:
            return None
        soup = BeautifulSoup(response.content, self.config.get_encoding())
        self._fill_article_with_meta_information(soup)
        self._fill_article_with_text(soup)
        self.article.url = self.full_url
        return self.article

def prepare_environment(base_path: pathlib.Path | str) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (pathlib.Path | str): Path where articles stores
    """
    if base_path.exists():
        try:
            shutil.rmtree(base_path)
        except (OSError, PermissionError):
            for item in base_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
    base_path.mkdir(parents=True, exist_ok=True)

def main() -> None:
    """
    Entrypoint for scraper module.
    """
    config_path = CRAWLER_CONFIG_PATH

    if not config_path.exists():
        print("Configuration file not found!")
        return

    try:
        config = Config(config_path)
    except (IncorrectSeedURLError, NumberOfArticlesOutOfRangeError,
            IncorrectNumberOfArticlesError, IncorrectHeadersError,
            IncorrectEncodingError, IncorrectTimeoutError, IncorrectVerifyError) as exc:
        print(f"Configuration error: {exc}")
        return
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to read configuration file: {exc}")
        return

    assets_path = pathlib.Path("tmp/articles")
    prepare_environment(assets_path)

    try:
        crawler = CrawlerRecursive(config)
        crawler.find_articles()
    except IncorrectSeedURLError as exc:
        print(f"Seed URL error: {exc}")
        return
    except RequestException as exc:
        print(f"Network error during crawling: {exc}")
        return

    print(f"Found {len(crawler.urls)} articles")
    for idx, url in enumerate(crawler.urls[:config.get_num_articles()], start=1):
        parser = HTMLParser(url, idx, config)
        try:
            article = parser.parse()
        except requests.RequestException as exc:
            print(f"Network error parsing article {idx}: {exc}")
            continue
        except (AttributeError, ValueError) as exc:
            print(f"Parsing error for article {idx}: {exc}")
            continue

        if article:
            to_raw(article)
            to_meta(article)
            print(f"Saved article {idx}: {url}")
        else:
            print(f"Failed to parse article {idx}: {url}")

if __name__ == "__main__":
    main()

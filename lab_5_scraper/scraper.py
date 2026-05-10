"""
Crawler implementation.
"""

import datetime
import json
import pathlib
import re
import shutil
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from requests.exceptions import RequestException

from core_utils.article.article import Article
from core_utils.article.io import to_meta, to_raw
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
        self._seed_urls: list[str] = self._config_dto.seed_urls
        self._num_articles: int = self._config_dto.total_articles
        self._headers: dict[str, str] = self._config_dto.headers
        self._encoding: str = self._config_dto.encoding
        self._timeout: int = self._config_dto.timeout
        self._should_verify_certificate: bool = self._config_dto.should_verify_certificate
        self._headless_mode: bool = self._config_dto.headless_mode

        if "User-Agent" not in self._headers:
            self._headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

    def config_content(self) -> ConfigDTO | None:
        """Backward compatibility for tests."""
        return self._config_dto

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
        if not (isinstance(dto.seed_urls, list) and dto.seed_urls and
            all(re.match(r'^https?://(www\.)?', url) for url in dto.seed_urls)):
            raise IncorrectSeedURLError("Invalid seed URLs")

        total = dto.total_articles
        if not isinstance(total, int):
            raise IncorrectNumberOfArticlesError(
                "total_articles_to_find_and_parse must be an integer"
            )
        if not 1 <= total <= 150:
            if total < 1:
                raise IncorrectNumberOfArticlesError(
                    "total_articles_to_find_and_parse must be a positive integer"
                )
            raise NumberOfArticlesOutOfRangeError(
                "total_articles_to_find_and_parse must be in range 1..150"
            )

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
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self._headless_mode

def make_request(url: str, config: Config) -> requests.Response | None:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    if url.startswith('#') or url.startswith('javascript:'):
        return None

    try:
        response = requests.get(
            url,
            headers=config.get_headers(),
            timeout=config.get_timeout(),
            verify=config.get_verify_certificate(),
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
        self._base_url: str = ""

    def _extract_url(self, article_bs: Tag) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.Tag): Tag instance

        Returns:
            str: Url from HTML
        """
        href = article_bs.get("href")
        if not href or not isinstance(href, str):
            return ""
        return urljoin(self._base_url, href)

    def find_articles(self) -> None:
        """
        Find articles.
        """
        needed = self.config.get_num_articles()
        queue = list(self.config.get_seed_urls())
        visited = set()

        while queue and len(self.urls) < needed:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            response = make_request(url, self.config)
            if not response or response.status_code != 200:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            self._base_url = url

            for link in soup.find_all('a', href=True):
                full_url = self._extract_url(link)
                if not full_url:
                    continue
                if full_url not in self.urls and len(self.urls) < needed:
                    self.urls.append(full_url)
                if full_url not in visited and len(self.urls) < needed:
                    queue.append(full_url)

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
    STATE_FILE = pathlib.Path("tmp/crawler_state.json")

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the CrawlerRecursive class.

        Args:
            config (Config): Configuration
        """
        super().__init__(config)
        seed_urls = self.config.get_seed_urls()
        self.start_url = seed_urls[0]
        self.start_domain = urlparse(self.start_url).netloc
        self.num_articles = self.config.get_num_articles()
        self.url_pattern = re.compile(r"/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+\.?html?$")
        self._visited: set[str] = set()
        self._load_state()

    def _save_state(self) -> None:
        """Save current crawler state to file."""
        state = {
            "urls": self.urls,
            "visited": list(self._visited),
        }
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> None:
        """Load previous crawler state from file if exists."""
        if self.STATE_FILE.exists():
            with open(self.STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.urls = state.get("urls", [])
            self._visited = set(state.get("visited", []))

    def _crawl(self, url: str, depth: int = 0) -> None:
        """
        Recursively crawl a single URL to collect article links.

        Args:
            url (str): URL to crawl
        """
        if depth > 10 or len(self.urls) >= self.num_articles or url in self._visited:
            return
        self._visited.add(url)

        response = make_request(url, self.config)
        if not response or 'text/html' not in response.headers.get('Content-Type', ''):
            return

        try:
            soup = BeautifulSoup(response.content, 'html.parser')
        except (ValueError, UnicodeDecodeError, LookupError):
            return

        self._base_url = url

        for link in soup.find_all('a', href=True):
            full_url = self._extract_url(link)
            if not full_url:
                continue

            link_domain = urlparse(full_url).netloc
            if link_domain != self.start_domain:
                continue

            if self.url_pattern.search(full_url) and full_url not in self.urls:
                self.urls.append(full_url)
                self._save_state()
                if len(self.urls) >= self.num_articles:
                    return

            if len(self.urls) < self.num_articles:
                self._crawl(full_url, depth + 1)
                if len(self.urls) >= self.num_articles:
                    return

    def find_articles(self) -> None:
        """
        Find number of article urls requested.
        """
        if not self.start_url:
            return
        self._crawl(self.start_url)
        self._save_state()

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
        selectors = [
            'article', 'div.article-body', 'div.post-content', 'div.content',
            'div.entry-content', 'div.main-content', 'section.content'
        ]
        text_parts = []
        for selector in selectors:
            elements = article_soup.select(selector)
            if elements:
                for elem in elements:
                    text_parts.append(elem.get_text(strip=True))
                break

        if not text_parts:
            paragraphs = article_soup.find_all('p')
            if paragraphs:
                text_parts = [p.get_text(strip=True) for p in paragraphs]
            else:
                body = article_soup.find('body')
                if body:
                    for tag in body(['script', 'style']):
                        tag.decompose()
                    text = body.get_text(separator=' ', strip=True)
                    text_parts = [text]
                else:
                    text_parts = [article_soup.get_text(separator=' ', strip=True)]

        self.article.text = ' '.join(text_parts)

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

    def _find_date_published(self, data: Any) -> str | None:
        """Recursively search for 'datePublished' in JSON data."""
        if isinstance(data, dict):
            if 'datePublished' in data and isinstance(data['datePublished'], str):
                return data['datePublished']
            for value in data.values():
                result = self._find_date_published(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_date_published(item)
                if result:
                    return result
        return None

    def _extract_json_ld_date(self, soup: BeautifulSoup) -> str | None:
        """Extract date from JSON-LD script."""
        for script in soup.find_all('script', type='application/ld+json'):
            content = script.string
            if not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
                date = self._find_date_published(data)
                if date:
                    return date
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title."""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _extract_author(self, soup: BeautifulSoup) -> list[str]:
        """Extract article author(s)."""
        author_tag = soup.find('meta', {'name': 'author'})
        if author_tag:
            content = author_tag.get('content')
            if isinstance(content, str):
                return self._extract_authors(content)
            if isinstance(content, list) and content and isinstance(content[0], str):
                return self._extract_authors(content[0])
        return ["NOT FOUND"]

    def _extract_date_from_meta(self, soup: BeautifulSoup) -> str | None:
        """Extract date from meta tags."""
        for meta_name in ['date', 'pubdate', 'publish_date', 'article:published_time',
                          'og:article:published_time', 'article:modified_time']:
            tag = soup.find('meta', {'name': meta_name}) or (
                soup.find('meta', {'property': meta_name})
            )
            if tag:
                content = tag.get('content')
                if isinstance(content, str):
                    return content
                if isinstance(content, list) and content and isinstance(content[0], str):
                    return content[0]
        return None

    def _extract_date_from_time_tag(self, soup: BeautifulSoup) -> str | None:
        """Extract date from <time> element."""
        time_tag = soup.find('time')
        if time_tag:
            dt = time_tag.get('datetime') or time_tag.get('content') or (
                time_tag.get_text(strip=True)
            )
            if isinstance(dt, str):
                return dt
        return None

    def _extract_date_from_class(self, soup: BeautifulSoup) -> str | None:
        """Extract date from element with date-related class."""
        date_elem = soup.find(class_=re.compile(r'date|time|published', re.I))
        if date_elem:
            text = date_elem.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_date_from_data_attr(self, soup: BeautifulSoup) -> str | None:
        """Extract date from data-* attributes."""
        for attr in ['data-date', 'data-published', 'data-timestamp']:
            elem = soup.find(attrs={attr: True})
            if elem:
                value = elem.get(attr)
                if isinstance(value, str):
                    return value
        return None

    def _extract_date_string(self, soup: BeautifulSoup) -> str | None:
        """Try all date extraction strategies and return first found string."""
        strategies = [
            self._extract_date_from_meta,
            self._extract_date_from_time_tag,
            self._extract_json_ld_date,
            self._extract_date_from_class,
            self._extract_date_from_data_attr
        ]
        for strategy in strategies:
            date_str = strategy(soup)
            if date_str:
                return date_str
        return None

    def _extract_topics(self, soup: BeautifulSoup) -> list[str]:
        """Extract topics/keywords."""
        topics = []
        for meta_name in ['news_keywords', 'keywords', 'article:tag']:
            tag = soup.find('meta', {'name': meta_name}) or (
                soup.find('meta', {'property': meta_name})
            )
            if tag:
                content = tag.get('content')
                if isinstance(content, str):
                    topics.extend([t.strip() for t in content.split(',') if t.strip()])
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, str):
                            topics.extend([t.strip() for t in item.split(',') if t.strip()])
        if topics:
            return list(dict.fromkeys(topics))[:5]
        return []

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        self.article.title = self._extract_title(article_soup)
        self.article.author = self._extract_author(article_soup)

        date_str = self._extract_date_string(article_soup)
        if date_str:
            parsed = self.unify_date_format(date_str)
            if parsed:
                self.article.date = parsed

        self.article.topics = self._extract_topics(article_soup)

    def _parse_russian_no_time(
            self, match: re.Match, months: dict[str, int]
            ) -> datetime.datetime | None:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        month = months.get(month_name)
        if month is None:
            return None
        return datetime.datetime(year, month, day)

    def _parse_russian_with_time(
            self, match: re.Match, months: dict[str, int]
            ) -> datetime.datetime | None:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        month = months.get(month_name)
        if month is None:
            return None
        return datetime.datetime(year, month, day, hour, minute)

    def _parse_dot_date(self, match: re.Match, _: Any = None) -> datetime.datetime:
        day, month, year = map(int, match.groups())
        return datetime.datetime(year, month, day)

    def _parse_iso_date(self, match: re.Match, _: Any = None) -> datetime.datetime:
        year, month, day = map(int, match.groups())
        return datetime.datetime(year, month, day)

    def _parse_iso_with_time(self, match: re.Match, _: Any = None) -> datetime.datetime:
        year, month, day, hour, minute = map(int, match.groups())
        return datetime.datetime(year, month, day, hour, minute)

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
            (r'(\d{1,2})\s+([а-я]+)\s+(\d{4})', self._parse_russian_no_time),
            (r'(\d{1,2})\s+([а-я]+)\s+(\d{4}),\s+(\d{2}):(\d{2})', self._parse_russian_with_time),
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', self._parse_dot_date),
            (r'(\d{4})-(\d{2})-(\d{2})', self._parse_iso_date),
            (r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):\d{2}', self._parse_iso_with_time),
        ]
        result = None
        for pattern, parse_func in patterns:
            match = re.search(pattern, date_str)
            if match:
                result = parse_func(match, russian_months)
                if result is not None:
                    break
        return result

    def unify_date_format(self, date_str: str) -> datetime.datetime | None:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        result = self._parse_russian_date(date_str)
        if result is None:
            formats = [
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d',
                '%d/%m/%Y', '%m/%d/%Y', '%B %d, %Y', '%d %B %Y', '%d.%m.%Y'
            ]
            for fmt in formats:
                try:
                    result = datetime.datetime.strptime(date_str[:len(fmt)], fmt)
                    break
                except ValueError:
                    continue
        return result

    def parse(self) -> Article | None:
        """
        Parse each article.

        Returns:
            Article | bool: Article instance, False in case of request error
        """
        response = make_request(self.full_url, self.config)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
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
    base_path = pathlib.Path(base_path)
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

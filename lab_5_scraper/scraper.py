"""
Crawler implementation.
"""

# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable, unused-argument
import datetime
import json
import pathlib
import re
import requests
from bs4 import BeautifulSoup, Tag

from core_utils.article.article import Article
from core_utils.config_dto import ConfigDTO
from core_utils.article.io import to_raw, to_meta
from core_utils.constants import CRAWLER_CONFIG_PATH

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
        self.config_content = self._extract_config_content()
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
        if not isinstance(self.config_content.seed_urls, list):
            raise ValueError("seed_urls must be a list")

        if not self.config_content.seed_urls:
            raise ValueError("seed_urls cannot be empty")

        if (not isinstance(self.config_content.total_articles, int)
            or self.config_content.total_articles <= 0):
            raise ValueError("num_articles must be a positive integer")

        if not isinstance(self.config_content.headers, dict):
            raise ValueError("headers must be a dictionary")

        if not isinstance(self.config_content.encoding, str):
            raise ValueError("encoding must be a string")

        if not isinstance(self.config_content.timeout, int) or self.config_content.timeout <= 0:
            raise ValueError("timeout must be a positive integer")

        if not isinstance(self.config_content.should_verify_certificate, bool):
            raise ValueError("verify_certificate must be a boolean")

        if not isinstance(self.config_content.headless_mode, bool):
            raise ValueError("headless_mode must be a boolean")

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self.config_content.seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self.config_content.total_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self.config_content.headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self.config_content.encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self.config_content.timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self.config_content.should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self.config_content.headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    response = requests.get(
        url,
        headers=config.get_headers(),
        timeout=config.get_timeout(),
        verify=config.get_verify_certificate()
    )
    response.encoding = config.get_encoding()
    return response

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
        self.seed_urls = config.get_seed_urls()
        self.urls = []
        self.visited_urls = set()
        self.article_urls = []
        self.url_pattern = r'^https?://[^\s]+'

    def _extract_url(self, article_bs: Tag) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.Tag): Tag instance

        Returns:
            str: Url from HTML
        """
        href_tag = article_bs.find('a')
        if href_tag:
            href = href_tag.get('href')
            if href and isinstance(href, str):
                if href.startswith(('http://', 'https://')):
                    return href
                base_url = str(article_bs)
                if '/' in base_url:
                    base_url = '/'.join(base_url.split('/')[:-1])
                if href.startswith('/'):
                    href = href[1:]
                return f"{base_url}/{href}"
        return ""

    def find_articles(self) -> None:
        """
        Find articles.
        """
        for url in self.config.get_seed_urls():
            response = make_request(url, self.config)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href and isinstance(href, str):
                        if href.startswith(('http://', 'https://')):
                            full_url = href
                        elif href.startswith('/'):
                            base_parts = url.split('/')
                            base_url = f"{base_parts[0]}//{base_parts[2]}"
                            full_url = base_url + href
                        else:
                            base_url = '/'.join(url.split('/')[:-1])
                            full_url = base_url + '/' + href
                        if full_url not in self.urls:
                            if len(self.urls) < self.config.get_num_articles():
                                self.urls.append(full_url)

    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.seed_urls


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
        self.start_url = self.config.get_seed_urls()[0] if self.config.get_seed_urls() else ""
        self.num_articles = self.config.get_num_articles()
        self.url_pattern = r"/\d{4}/\d{2}/\d{2}/"
        self.visited_urls = set()

    def find_articles(self) -> None:
        """
        Find number of article urls requested.
        """
        def crawl_recursive(url: str) -> None:
            if len(self.urls) >= self.num_articles:
                return
            if url in self.visited_urls:
                return

            response = make_request(url, self.config)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href and isinstance(href, str):
                        if href.startswith(('http://', 'https://')):
                            full_url = href
                        elif href.startswith('/'):
                            base_parts = url.split('/')
                            base_url = f"{base_parts[0]}//{base_parts[2]}"
                            full_url = base_url + href
                        else:
                            base_url = '/'.join(url.split('/')[:-1])
                            full_url = base_url + '/' + href
                        if (re.search(self.url_pattern, full_url)
                            and full_url not in self.visited_urls):
                            if len(self.urls) < self.num_articles:
                                self.urls.append(full_url)
                                self.visited_urls.add(full_url)
                        if len(self.urls) < self.num_articles:
                            crawl_recursive(full_url)

        if self.start_url:
            crawl_recursive(self.start_url)


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
        if topics:
            self.article.topics = topics[:5]

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%B %d, %Y',
            '%d %B %Y'
        ]

        for fmt in date_formats:
            try:
                return datetime.datetime.strptime(date_str[:len(fmt)], fmt)
            except ValueError:
                continue

        return datetime.datetime.now()

    def parse(self) -> Article | bool:
        """
        Parse each article.

        Returns:
            Article | bool: Article instance, False in case of request error
        """
        response = make_request(self.full_url, self.config)
        if not response:
            return False

        soup = BeautifulSoup(response.text, self.config.get_encoding())
        self._fill_article_with_meta_information(soup)
        self._fill_article_with_text(soup)

        return self.article


def prepare_environment(base_path: pathlib.Path | str) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (pathlib.Path | str): Path where articles stores
    """
    path = pathlib.Path(base_path)
    if path.exists():
        for item in path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                for subitem in item.rglob('*'):
                    if subitem.is_file():
                        subitem.unlink()
                item.rmdir()
        path.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """
    Entrypoint for scraper module.
    """
    config_path = pathlib.Path("scraper_config.json")
    if not config_path.exists():
        print("Configuration file not found!")
        return

    try:
        config = Config(config_path)

        assets_path = pathlib.Path("tmp/articles")
        prepare_environment(assets_path)

        crawler = CrawlerRecursive(config)
        crawler.find_articles()

        print(f"Found {len(crawler.urls)} articles")

        for i, url in enumerate(crawler.urls[:config.get_num_articles()]):
            parser = HTMLParser(url, i + 1, config)
            article = parser.parse()
            if article and isinstance(article, Article):
                to_raw(article)
                to_meta(article)
                print(f"Saved article {i + 1}: {url}")
            else:
                print(f"Failed to parse article {i + 1}: {url}")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except requests.RequestException as e:
        print(f"Network error: {e}")
    except IOError as e:
        print(f"File system error: {e}")


if __name__ == "__main__":
    main()

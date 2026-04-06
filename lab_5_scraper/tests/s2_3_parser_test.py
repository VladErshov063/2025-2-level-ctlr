"""
Parser realization validation.
"""

# pylint: disable=no-member, no-name-in-module, assignment-from-no-return
import random
import unittest

import pytest

from core_utils.article.article import Article
from core_utils.constants import CRAWLER_CONFIG_PATH
from lab_5_scraper.scraper import Config, Crawler, HTMLParser


class HTMLParserTest(unittest.TestCase):
    """
    A class for testing Parser abstraction.
    """

    def setUp(self) -> None:
        """
        Define start instructions for HTMLParserTest class.
        """
        self.config = Config(CRAWLER_CONFIG_PATH)

        self.crawler = Crawler(self.config)
        self.crawler.find_articles()
        self.parser = HTMLParser(random.choice(self.crawler.urls), 1, self.config)
        self.return_value = self.parser.parse()

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_3_HTML_parser_check
    @pytest.mark.lab_5_scraper
    def test_html_parser_instantiation(self) -> None:
        """
        Ensure Parser is instantiated correctly.
        """
        parser = HTMLParser(random.choice(self.crawler.urls), 1, config=self.config)
        self.assertTrue(
            hasattr(parser, "article"), "Parser instance must possess 'article' attribute"
        )
        message = "Attribute 'article' of Parser instance must be an instance of Article"
        self.assertIsInstance(parser.article, Article, message)

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_3_HTML_parser_check
    @pytest.mark.lab_5_scraper
    def test_html_parser_parse_return_value_basic(self) -> None:
        """
        Ensure Parser.parser() returns Article with filled text field.
        """
        self.assertIsInstance(
            self.return_value, Article, "parse() method must return Article instance"
        )
        self.assertTrue(
            self.return_value.article_id, "parse() method must return Article with filled id"
        )
        message = "parse() method must return an Article instance with filled text"
        self.assertTrue(self.return_value.text, message)

    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_3_HTML_parser_check
    @pytest.mark.lab_5_scraper
    def test_html_parser_parse_return_value_medium(self) -> None:
        """
        Ensure Parser.parser() returns Article with filled title and author.
        """
        self.assertTrue(
            self.return_value.title, "parse() method must return Article with filled title"
        )
        message = "parse() method must return an Article instance with filled author"
        self.assertTrue(self.return_value.author, message)

    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_3_HTML_parser_check
    @pytest.mark.lab_5_scraper
    def test_html_parser_parse_method_advanced(self) -> None:
        """
        Ensure Parser.parser() returns Article with filled date field.
        """
        message = "parse() method must return an Article instance with filled date"
        self.assertTrue(self.return_value.date, message)

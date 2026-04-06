"""
Crawler configuration validation.
"""

# pylint: disable=no-name-in-module
import json
import shutil
import unittest
from pathlib import Path
from typing import Any

import pytest

from admin_utils.test_params import TEST_CRAWLER_CONFIG_PATH, TEST_PATH
from core_utils.constants import CRAWLER_CONFIG_PATH, TIMEOUT_LOWER_LIMIT, TIMEOUT_UPPER_LIMIT
from lab_5_scraper import scraper
from lab_5_scraper.scraper import (
    IncorrectEncodingError,
    IncorrectHeadersError,
    IncorrectNumberOfArticlesError,
    IncorrectSeedURLError,
    IncorrectTimeoutError,
    IncorrectVerifyError,
    NumberOfArticlesOutOfRangeError,
)
from lab_5_scraper.tests.config_generator import generate_config

print("Stage 1A: Validating Crawler Config")
print("Starting tests with received config")


class ExceptionIsNotRaised(Exception):
    """
    No exception was raised.
    """


class ExtendedTestCase(unittest.TestCase):
    """
    Enable messaging when assertRaises is triggered.
    """

    # pylint: disable=invalid-name
    def assertRaisesWithMessage(
        self, msg: str, exception: Any, func: Any, *args: Path, **kwargs: Any
    ) -> None:
        """
        Method assertRaises counterparts with enabled messaging.

        Args:
            msg (str): Error message
            exception (Any): Exception
            func (Any): Function
            *args (Path): Arguments
            **kwargs (Any): Options
        """
        try:
            func(*args, **kwargs)
            print(msg)
            raise ExceptionIsNotRaised
        except ExceptionIsNotRaised:
            raise AssertionError(msg) from ExceptionIsNotRaised
        except Exception as inst:  # pylint: disable=broad-except
            self.assertEqual(exception, type(inst), msg)


# pylint: disable=too-many-instance-attributes
class CrawlerConfigCheck(ExtendedTestCase):
    """
    A class for Crawler configuration validation.
    """

    def setUp(self) -> None:
        """
        Define start instructions for CrawlerConfigCheck class.
        """
        with CRAWLER_CONFIG_PATH.open() as file:
            self.reference = json.load(file)

        self.seed_urls_correct = self.reference["seed_urls"]
        self.num_articles_correct = self.reference["total_articles_to_find_and_parse"]
        self.headers_correct = self.reference["headers"]
        self.timeout_correct = self.reference["timeout"]
        self.encoding_correct = self.reference["encoding"]
        self.should_verify_certificate = self.reference["should_verify_certificate"]
        self.headless_mode = self.reference["headless_mode"]

        self.seed_urls_incorrect = ["https://sample.com/", True, 1, ["does_not_match_pattern"]]
        self.num_articles_incorrect = [-5, False, {1: 2}]
        self.headers_incorrect = [True, 1, "headers"]
        self.timeout_incorrect = [
            "five secs",
            {False: 5},
            TIMEOUT_LOWER_LIMIT - 5,
            TIMEOUT_UPPER_LIMIT + 5,
        ]
        self.encoding_incorrect = [5, False, [1, 2, 3]]
        self.verify_incorrect = ["verify", {1: 2}, (1, 2)]
        self.headless_incorrect = ["false", {1: 4}, (1, 2, 3)]

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_base_urls_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_seed_urls in self.seed_urls_incorrect:
            generate_config(
                seed_urls=incorrect_seed_urls,
                num_articles=self.num_articles_correct,
                timeout=self.timeout_correct,
                headers=self.headers_correct,
                encoding=self.encoding_correct,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=self.headless_mode,
            )

            error_message = """Checking that scraper can handle incorrect seed_urls inputs.
    Seed URLs must be a list of strings, not a single string"""
            self.assertRaisesWithMessage(
                error_message, IncorrectSeedURLError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
            )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_num_urls_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_num_urls in self.num_articles_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=incorrect_num_urls,
                timeout=self.timeout_correct,
                headers=self.headers_correct,
                encoding=self.encoding_correct,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=self.headless_mode,
            )

            error_message = """Checking that scraper can handle incorrect num articles inputs.
    Num articles must be a positive integer."""
            self.assertRaisesWithMessage(
                error_message,
                IncorrectNumberOfArticlesError,
                scraper.Config,
                TEST_CRAWLER_CONFIG_PATH,
            )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_num_urls_too_large_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        generate_config(
            seed_urls=self.seed_urls_correct,
            num_articles=1000000,
            timeout=self.timeout_correct,
            headers=self.headers_correct,
            encoding=self.encoding_correct,
            should_verify_certificate=self.should_verify_certificate,
            headless_mode=self.headless_mode,
        )

        error_message = """Checking that scraper can handle incorrect num articles inputs.
Num articles must not be too large"""
        self.assertRaisesWithMessage(
            error_message,
            NumberOfArticlesOutOfRangeError,
            scraper.Config,
            TEST_CRAWLER_CONFIG_PATH,
        )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_timeout_too_large_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_timeout in self.timeout_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=self.num_articles_correct,
                timeout=incorrect_timeout,
                headers=self.headers_correct,
                encoding=self.encoding_correct,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=self.headless_mode,
            )

            error_message = """Checking that scraper can handle incorrect timeout inputs.
        Num articles must be an integer between 0 and 60. 0 is a valid value"""
            self.assertRaisesWithMessage(
                error_message, IncorrectTimeoutError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
            )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_headers_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_headers in self.headers_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=self.num_articles_correct,
                timeout=self.timeout_correct,
                headers=incorrect_headers,
                encoding=self.encoding_correct,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=self.headless_mode,
            )

        error_message = """Checking that scraper can handle incorrect headers.
Headers must be a dictionary with string keys and string values"""
        self.assertRaisesWithMessage(
            error_message, IncorrectHeadersError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
        )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_encoding_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_encoding in self.encoding_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=self.num_articles_correct,
                timeout=self.timeout_correct,
                headers=self.headers_correct,
                encoding=incorrect_encoding,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=self.headless_mode,
            )

        error_message = """Checking that scraper can handle incorrect encoding.
    Encoding must be a string"""
        self.assertRaisesWithMessage(
            error_message, IncorrectEncodingError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
        )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_verify_cert_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_verify in self.verify_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=self.num_articles_correct,
                timeout=self.timeout_correct,
                headers=self.headers_correct,
                encoding=self.encoding_correct,
                should_verify_certificate=incorrect_verify,
                headless_mode=self.headless_mode,
            )

        error_message = """Checking that scraper can handle incorrect verify certificate argument.
    Verify certificate must be either True or False"""
        self.assertRaisesWithMessage(
            error_message, IncorrectVerifyError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
        )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_incorrect_headless_config_param(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        for incorrect_headless in self.headless_incorrect:
            generate_config(
                seed_urls=self.seed_urls_correct,
                num_articles=self.num_articles_correct,
                timeout=self.timeout_correct,
                headers=self.headers_correct,
                encoding=self.encoding_correct,
                should_verify_certificate=self.should_verify_certificate,
                headless_mode=incorrect_headless,
            )

        error_message = """Checking that scraper can handle headless mode argument.
    Headless mode must be either True or False"""
        self.assertRaisesWithMessage(
            error_message, IncorrectVerifyError, scraper.Config, TEST_CRAWLER_CONFIG_PATH
        )

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_config_initialization(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        generate_config(
            seed_urls=self.seed_urls_correct,
            num_articles=self.num_articles_correct,
            timeout=self.timeout_correct,
            headers=self.headers_correct,
            encoding=self.encoding_correct,
            should_verify_certificate=self.should_verify_certificate,
            headless_mode=self.headless_mode,
        )
        attr_names = [
            "path_to_config",
            "_seed_urls",
            "_num_articles",
            "_headers",
            "_encoding",
            "_timeout",
            "_should_verify_certificate",
        ]
        config = scraper.Config(TEST_CRAWLER_CONFIG_PATH)
        all_attrs = [hasattr(config, attr_name) for attr_name in attr_names]
        error_message = """Checking that scraper saves relevant data to attributes."""
        self.assertTrue(all(all_attrs), msg=error_message)

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_1_crawler_config_check
    @pytest.mark.lab_5_scraper
    def test_config_getters(self) -> None:
        """
        Config class returns error message and exit code 1 with incorrect config params.
        """
        generate_config(
            seed_urls=self.seed_urls_correct,
            num_articles=self.num_articles_correct,
            timeout=self.timeout_correct,
            headers=self.headers_correct,
            encoding=self.encoding_correct,
            should_verify_certificate=self.should_verify_certificate,
            headless_mode=self.headless_mode,
        )
        config = scraper.Config(TEST_CRAWLER_CONFIG_PATH)
        getters = [
            config.get_seed_urls,
            config.get_num_articles,
            config.get_headers,
            config.get_encoding,
            config.get_timeout,
            config.get_verify_certificate,
            config.get_headless_mode,
        ]
        values = [
            self.seed_urls_correct,
            self.num_articles_correct,
            self.headers_correct,
            self.encoding_correct,
            self.timeout_correct,
            self.should_verify_certificate,
            self.headless_mode,
        ]
        self.assertTrue(all(method() == value for method, value in zip(getters, values)))

    def tearDown(self) -> None:
        """
        Define final instructions for CrawlerConfigCheck class.
        """
        if TEST_PATH.exists():
            shutil.rmtree(TEST_PATH)

# pylint: disable=too-many-arguments, too-many-positional-arguments
"""
Generate config with flexible params for testing purposes.
"""

import json
import shutil
from pathlib import Path

from admin_utils.test_params import TEST_CRAWLER_CONFIG_PATH, TEST_PATH


def generate_config(
    seed_urls: list,
    num_articles: int,
    headers: dict[str, str],
    encoding: str,
    timeout: int,
    should_verify_certificate: bool,
    headless_mode: bool,
    path: Path = TEST_CRAWLER_CONFIG_PATH,
) -> None:
    """
    Generate scraper_config.py for testing.

    Args:
        seed_urls (list): Seed urls
        num_articles (int): Number articles
        headers (dict[str, str]): Headers
        encoding (str): Encoding
        timeout (int): Number of seconds to wait for response
        should_verify_certificate (bool): Should verify certificate or not
        headless_mode (bool): Require headless mode or not
        path (Path, optional): Path to test crawler configuration.
            Defaults to TEST_CRAWLER_CONFIG_PATH.
    """
    config = {
        "seed_urls": seed_urls,
        "total_articles_to_find_and_parse": num_articles,
        "headers": headers,
        "encoding": encoding,
        "timeout": timeout,
        "should_verify_certificate": should_verify_certificate,
        "headless_mode": headless_mode,
    }

    if path.exists():
        shutil.rmtree(TEST_PATH)
    TEST_PATH.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file)

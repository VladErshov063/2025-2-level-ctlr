"""
Check raw dataset volume.
"""

import shutil
import unittest

import pytest

from admin_utils.test_params import TEST_PATH
from lab_5_scraper.tests.utils import scraper_setup


class VolumeCheckTest(unittest.TestCase):
    """
    Check folder volume is appropriate.
    """

    def setUp(self) -> None:
        """
        Define start instructions for VolumeCheckTest class.
        """
        scraper_setup()

    @pytest.mark.mark4
    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_4_dataset_volume_check
    @pytest.mark.lab_5_scraper
    def test_folder_is_not_empty(self) -> None:
        """
        Ensure there are collected articles.
        """
        self.assertTrue(any(TEST_PATH.iterdir()), msg="ASSETS_PATH directory is empty")

    @pytest.mark.mark6
    @pytest.mark.mark8
    @pytest.mark.mark10
    @pytest.mark.stage_2_4_dataset_volume_check
    @pytest.mark.lab_5_scraper
    def test_folder_has_equal_number_of_files(self) -> None:
        """
        Ensure there are equal number of raw and meta files.
        """
        metas, raws = 0, 0
        for file in TEST_PATH.iterdir():
            if file.name.endswith("_raw.txt"):
                raws += 1
            if file.name.endswith("_meta.json"):
                metas += 1
        message = "Collected dataset do not contain equal number of raw_articles and metas"
        self.assertEqual(metas, raws, msg=message)

    def tearDown(self) -> None:
        """
        Define start instructions for VolumeCheckTest class.
        """
        shutil.rmtree(TEST_PATH)

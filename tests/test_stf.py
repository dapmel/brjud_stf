"""STF tests."""
from datetime import date, datetime
from typing import List
import os
import psycopg2 as pg
import pytest
import yaml

from db_utils.db_config import config
from db_utils.db_testing import DBTester
import STF

with open("utils/config.yml") as ymlfile:
    cfg = yaml.safe_load(ymlfile)


class TestDBUtils:
    """Test database utilities."""

    def test_config_file_exception(self):
        """Test validation of database configuration file."""
        test_data: dict = {"db_params":
                           {'host': 'localhost', 'database': 'jusdata_test',
                            'user': 'postgres'}}
        filename: str = "test_params.yml"
        path_with_file = f"db_utils/{filename}"
        with open(path_with_file, "w") as outfile:
            yaml.dump(test_data, outfile, default_flow_style=False)

        # Check test file creation
        assert os.path.isfile(path_with_file)

        with pytest.raises(Exception) as exc_info:
            config(filename)
        assert exc_info.value.args[0] == \
            f"Section 'password' not found in '{filename}'"

        os.remove(path_with_file)
        # Check test file deletion
        assert os.path.isfile(path_with_file) is False

    def test_config_file_integrity(self):
        """Test keys of validated database configuration file."""
        params = config()
        for key in ["host", "database", "user", "password"]:
            assert key in params

    def test_database_and_tables(self):
        """Test database availability and existence/creation of log table.

        Other tests will create tables as well. This test simply allows
        detailed testing of the general table creation mechanism if needed.
        """
        self.db_params = cfg["testing"]["db_params"]

        assert pg.connect(**self.db_params)

        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(cfg["testing"]["sql"]["drop_all"])
            conn.commit()

            # Create ``stf_data`` table and test its existence
            DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)
            curs.execute(cfg["testing"]["sql"]["find_table"], ("stf_data",))
            assert curs.fetchone()[0]

            # Create ``stf_scrap_log`` table  and test its existence
            DBTester("stf_scrap_log", cfg["sql"]["scrap_log"]["create"],
                     self.db_params)
            curs.execute(cfg["testing"]["sql"]["find_table"],
                         ("stf_scrap_log",))
            assert curs.fetchone()[0]


class TestSTFSearchScraper:
    """Test STF Search Scraper."""

    db_params = cfg["testing"]["db_params"]
    today_date: date = datetime.today().date()

    def test_search_scraper(self):
        """Test STF search scraper."""
        scraper = STF.SearchScraper(self.db_params)
        # step = 1 would generate errors as the starting id would always be
        # the same as the last id scraped
        scraper.step = 2

        # The start method returns True on successes
        status: bool = scraper.start(mode="max")
        assert status

    def test_search_logs(self):
        """Check integrity of data in ``stf_scrap_log`` table."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(cfg["sql"]["scrap_log"]["select"]["all"])
            data = curs.fetchall()
            assert len(data) == 46

    def test_processes_data(self):
        """Check integrity of data in ``stf_data`` table."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(cfg["sql"]["data"]["select"]["all"])
            data_rows: List(tuple) = curs.fetchall()
            assert len(data_rows) == 78


class TestSTFProcessScraper:
    """Test STF proccess scraper."""

    db_params = cfg["testing"]["db_params"]

    def test_details_scraping(self):
        """Test quality of scraping."""
        test_item = ("1418401", "00003950519360010000", 3, "IF",
                     datetime.strptime("23/11/1936", "%d/%m/%Y").date(), 1, 1,
                     datetime.strptime("10/4/2022", "%d/%m/%Y").date())

        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(cfg["testing"]["sql"]["drop_all"])
            conn.commit()

        # Create ``stf_data`` table
        DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)

        process_scraper = STF.ProcessScraper(self.db_params)

        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Insert testing item
            curs.execute(cfg["sql"]["data"]["insert"], test_item)
            conn.commit()

            process_scraper.start()

            # Check if all data was completed
            curs.execute(cfg["sql"]["data"]["select"]["incomplete"])
            data = curs.fetchall()
            assert len(data) == 0

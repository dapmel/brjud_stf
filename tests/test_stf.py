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

# Read yml config file
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

            # Create 'stf_data' table and test its existence
            DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)
            curs.execute(cfg["testing"]["sql"]["find_table"], ("stf_data",))
            assert curs.fetchone()[0]

            # Create 'stf_scrap_log' table  and test its existence
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
        """Test STF search scraper on ``max`` mode.

        This mode is being tested separately because it also serves to fill the
        testing table with real data to be tested.
        Other methods will be tested on the last method of the current class.
        """
        scraper = STF.SearchScraper(self.db_params)
        # step = 1 would generate errors as the starting id would always be
        # the same as the last id scraped
        scraper.step = 2

        # The start method returns True on successes
        assert scraper.start(mode="max")

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

    def test_exceptions(self):
        """Test special cases and exceptions."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(cfg["testing"]["sql"]["drop_all"])
            conn.commit()

        scraper = STF.SearchScraper(self.db_params)

        # Invalid ids must cause an error
        with pytest.raises(Exception) as exc_info:
            invalid_id = "invalid id"
            scraper.scrap_incidents(invalid_id)
        assert exc_info.value.args[0] == \
            f"Invalid id_stf: {invalid_id}"

        # Valid ids must return None
        assert scraper.scrap_incidents(468) is None

        # Ids without processes must not trigger a scraping attempt
        id_without_processes = 0
        assert not scraper.scrap_incidents(id_without_processes)

    def test_search_logs_modes(self):
        """Test ``min`` and ``code`` modes."""
        scraper = STF.SearchScraper(self.db_params)
        scraper.step = 2
        # On this context, a 'min' mode scrap must not find any process after a
        # 'max' mode scrap because the ids must have been already covered
        assert not scraper.start(mode="min")

        assert scraper.start(mode="code", code="Inq")

        # 'code' mode must require a code
        with pytest.raises(Exception) as exc_info:
            scraper.start(mode="code")
        assert exc_info.value.args[0] == \
            "'code' parameter must not be None on 'code' mode."


class TestSTFProcessScraper:
    """Test STF proccess scraper."""

    db_params = cfg["testing"]["db_params"]

    def test_details_scraping(self):
        """Test quality of scraping."""
        # Dummy which all fields can be filled during scraping
        test_item: tuple = (
            2641263, "00002994520000010000", 1, "ADPF",
            datetime.strptime("23/11/1936", "%d/%m/%Y").date(), 1, 1,
            datetime.strptime("10/4/2022", "%d/%m/%Y").date())
        # Dummy that does not have 'numeros_origem'
        test_item_2: tuple = (
            1406899, "00002994520000010000", 1, "ADPF",
            datetime.strptime("23/11/1936", "%d/%m/%Y").date(), 1, 1,
            datetime.strptime("10/4/2022", "%d/%m/%Y").date())
        test_items: List(tuple) = [test_item, test_item_2]
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Drop all existing tables
            curs.execute(cfg["testing"]["sql"]["drop_all"])
            conn.commit()

        # Create 'stf_data' table
        DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)
        process_scraper = STF.ProcessScraper(self.db_params)
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            # Insert testing items
            for test_item in test_items:
                curs.execute(cfg["sql"]["data"]["insert"], test_item)
                conn.commit()

            process_scraper.start()

            # Check if all processes were filled
            curs.execute(cfg["sql"]["data"]["select"]["incomplete"])
            data = curs.fetchall()
            assert len(data) == 0

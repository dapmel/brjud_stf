"""STF Scraper."""
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import date, datetime
from typing import Generator, List, Literal, Optional, Tuple
import logging
import lxml.html
import psycopg2 as pg
import re
import yaml
from utils.funcs import requester
from db_utils.db_config import config
from db_utils.db_testing import DBTester

with open("utils/config.yml") as ymlfile:
    cfg = yaml.safe_load(ymlfile)

logging.basicConfig(
    format=cfg["log"]["format"], datefmt="%H:%M:%S", level=logging.INFO)


class SearchScraper:
    """Scrap STF search based on a range of ids and write on database."""

    def __init__(self, db_params: dict = None) -> None:
        """Initiate state, test database and tables.

        ``self.code`` keeps the code provided on ``code`` mode.

        ``self.step`` defines how many processes must be scraped on each run.
        A value around ``200`` is recomended to reduce requests made to the
        server.
        """
        logging.info("Initializing SearchScraper")
        self.db_params: dict = db_params if db_params is not None else config()
        DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)
        DBTester("stf_scrap_log", cfg["sql"]["scrap_log"]["create"],
                 self.db_params)
        self.code: Optional[str] = None
        self.step: int = 200
        self.now: date = datetime.now().date()

    def scrap_incidents(self, id_stf: int) -> None:
        """Extract incidents from search pages and write to the database.

        This method writes to two tables:

        ``scrap_log`` keeps a record of the last id scraped of each process
        type.

        ``stf_data`` stores data of all processes. ``scrap_incidents`` will
        write part of processes data to the database. The remaining columns
        will be filled by ``ProcessScraper.start()``.
        """
        # Disable this to avoid logging each ID scraped
        logging.info(f"Searching id {id_stf}")
        try:
            search_html: lxml.html.HtmlElement = requester(
                cfg["urls"]["search"].format(num=id_stf))
        except lxml.etree.ParserError:
            raise Exception(f"Invalid id_stf: {id_stf}")
        items: List[lxml.html.HtmlElement] = search_html.xpath("//table/tr")

        if len(items) == 0:
            return
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            for item in items:
                classe_processo_sigla: str = item.xpath(
                    "./td[position()=1]/a/text()")[0].split(" ")[0]
                # Only parse processes with given self.code
                if self.code is not None \
                        and classe_processo_sigla != self.code:
                    continue

                incidente: int = item.xpath(
                    "./td[position()=1]/a/@href")[0].split("=")[1]
                numero_unico: str = item.xpath("./td[position()=2]/text()")[0]\
                    .replace(".", "").replace("-", "")

                data_str: str = item.xpath(
                    "./td[position()=3]/text()")[0]
                data_protocolo: date = datetime.strptime(
                    data_str, "%d/%m/%Y").date()

                meio: str = item.xpath("./td[position()=4]/text()")[0]
                if meio == "Físico":
                    meio_id: int = 1
                elif meio == "Eletrônico":
                    meio_id = 2

                tipo: str = item.xpath("./td[position()=5]/text()")[0]
                if tipo == "Público":
                    tipo_id: int = 1
                elif tipo == "Segredo de Justiça":
                    tipo_id = 2
                elif tipo == "Sigiloso":
                    tipo_id = 3

                # Scrap log table
                curs.execute(cfg["sql"]["scrap_log"]["insert"],
                             (classe_processo_sigla, id_stf, self.now))
                conn.commit()
                # Data table
                curs.execute(cfg["sql"]["data"]["insert"], (
                    incidente, numero_unico, id_stf, classe_processo_sigla,
                    data_protocolo, meio_id, tipo_id, self.now))
                conn.commit()

    def calc_start(self, mode: Literal["min", "max", "code"]) -> int:
        """Calculate starting id based on the scraping mode."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            if mode == "max":
                curs.execute(
                    cfg["sql"]["scrap_log"]["select"]["id"]["highest"])
            elif mode == "min":
                curs.execute(cfg["sql"]["scrap_log"]["select"]["id"]["lowest"])
            elif mode == "code":
                curs.execute(cfg["sql"]["scrap_log"]["select"]["code"],
                             (self.code,))

            data: List[Tuple[int]] = curs.fetchall()
            try:
                return data[0][0]
            except IndexError:
                # Table is empty
                return 1

    def start(self, *,
              mode: Literal["min", "max", "code"],
              code: str = None) -> bool:
        """Calculate start id, run scrap pool and check retrieved data.

        There are three modes available to extract data from STF search:
        ``max`` starts from the highest id scraped,
        ``min`` starts from the lowest id scraped, and
        ``code`` starts from the highest id scraped of a given code.

        Use ``max`` mode if this is the first run.
        """
        self.code = code
        if mode == "code" and self.code is None:
            raise ValueError(
                "'code' parameter must not be None on 'code' mode.")

        start: int = self.calc_start(mode)
        ids = range(start, start+self.step)
        with ThreadPoolExecutor(cfg["threads"]["max_workers"]) as exec:
            futures = (exec.submit(self.scrap_incidents, id)
                       for id in ids)
            for future in as_completed(futures):
                future.result()

        # This can be used to stop recursion when no more data can be found
        after_update: int = self.calc_start(mode)
        if after_update == start:
            # No ids found within range
            logging.info("No new ids found in current id range. Done.")
            return False
        else:
            return True


class ProcessScraper:
    """Scrap detailed processes data."""

    def __init__(self, db_params: dict = None):
        """Initialize state, test ``stf_data`` table.

        All fields required by the database are added to the state for a better
        control of type hinting.
        """
        self.classe_processo: str = ""
        self.partes: List[Tuple[str, str]] = []
        self.assuntos: List[str] = []
        self.orgao_origem: str = ""
        self.origem: str = ""
        self.numeros_origem: List[str] = []
        self.scrap_date: date = datetime.now().date()
        self.db_params: dict = db_params if db_params is not None else config()
        DBTester("stf_data", cfg["sql"]["data"]["create"], self.db_params)

    def _parse_process(self, incidente: int) -> None:
        """Parse 'process' page."""
        # Dados gerais
        processo_html: lxml.html.HtmlElement = requester(
            cfg["urls"]["details"]["process"].format(incidente=incidente))

        classe_processo: str = processo_html.xpath(
            cfg["xpath"]["process"]["classe_processo"])
        self.classe_processo = classe_processo if len(classe_processo) else ""

    def _parse_parts(self, incidente: int) -> None:
        """Parse 'parts' page."""
        # Partes do processo
        partes_html: lxml.html.HtmlElement = requester(
            cfg["urls"]["details"]["parties"].format(incidente=incidente))
        partes_list: List[lxml.html.HtmlElement] = partes_html.xpath(
            cfg["xpath"]["process"]["partes_list"])
        if len(partes_list):
            for parte in partes_list:
                tipo: str = parte.xpath(
                    "./div[@class='detalhe-parte']/text()")[0]
                nome: str = parte.xpath("./div[@class='nome-parte']/text()")[0]
                self.partes.append((tipo, nome))

    def _parse_incident(self, incidente: int) -> None:
        """Parse 'incident' page."""
        # Detalhes do processo
        detalhes_html: lxml.html.HtmlElement = requester(
            cfg["urls"]["details"]["infos"].format(incidente=incidente))
        assuntos: List[lxml.html.HtmlElement] = detalhes_html.xpath(
            "//ul[@style='list-style:none;']/li")
        if len(assuntos):
            for assunto in assuntos:
                assunto = assunto.xpath("text()")[0]
                assunto_items: List[str] = assunto \
                    .replace("||", "|").split("|")
                self.assuntos.append("; ".join(assunto.strip()
                                               for assunto in assunto_items))

        # A positional approach could be used but the tags positions might not
        # be the same across all processes.

        # Looks for tags that contain the 'Origem:' text
        for item in detalhes_html.xpath("//*[text()[contains(.,':')]]"):
            # If it is an exact match
            if item.xpath("./text()")[0].strip() == "Data de Protocolo:":
                # Get next sibiling's text
                raw_date = item.getnext().xpath("text()")[0].strip()
                if raw_date != "":
                    self.data_protocolo = datetime \
                        .strptime(raw_date, "%d/%m/%Y").date()

            if item.xpath("./text()")[0].strip() == "Órgão de Origem:":
                self.orgao_origem = item.getnext().xpath("text()")[0].strip()

            if item.xpath("./text()")[0].strip() == "Origem:":
                self.origem = item.getnext().xpath("text()")[0].strip()

            if item.xpath("./text()")[0].strip() == "Número de Origem:":
                nums = item.getnext().xpath("text()")[0]
                self.numeros_origem = re.sub(r"[\n\t\s]*", "", nums).split(",")
                if(len(self.numeros_origem[0])) == 0:
                    self.numeros_origem = []

    def scrap_process(self, incidente: int) -> None:
        """Scrap process and save parsed data."""
        logging.info(f"Saving details from {incidente}")
        self._parse_process(incidente)
        self._parse_parts(incidente)
        self._parse_incident(incidente)

        # Lists must be converted to strings before writing to DB for now
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            payload = (self.classe_processo, self.partes, self.assuntos,
                       self.orgao_origem, self.origem, self.numeros_origem,
                       self.scrap_date, incidente)
            curs.execute(cfg["sql"]["data"]["update"], payload)
            conn.commit()

    def retrive_incidents(self) -> Generator[Tuple[int], None, None]:
        """Yield incidents that don't have any detailed data from DB."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(cfg["sql"]["data"]["select"]["incomplete"])
            yield from curs

    def start(self) -> bool:
        """Scrap data and fill incomplete processes."""
        with ThreadPoolExecutor(cfg["threads"]["max_workers"]) as exec:
            futures = (exec.submit(self.scrap_process, i[0])
                       for i in self.retrive_incidents())
            for future in as_completed(futures):
                future.result()

        return True

"""STF Scraper.

All classes accept database parameters on instance for testing purposes.
"""
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import date, datetime
from typing import Generator, List, Literal, Tuple
import logging
import lxml.html
import psycopg2 as pg
import re
from utils.funcs import requester, requester2
from db_utils.db_config import config
from db_utils.db_testing import db_testing
import utils.params as params

logging.basicConfig(
    format="[%(asctime)s %(funcName)s():%(lineno)s]%(levelname)s: %(message)s",
    datefmt="%H:%M:%S", level=logging.INFO)


class SearchScraper:
    """Scrap STF search."""

    def __init__(self, db_params: dict = None) -> None:
        """Initiate state, test database and tables."""
        logging.info("Initializing SearchScraper")
        self.db_params: dict = db_params if db_params is not None else config()
        db_testing("stf_data", params.sql_stf_data_table, self.db_params)
        db_testing("stf_scrap_log", params.sql_scrap_log_table, self.db_params)
        self.step: int = 200
        self.now: date = datetime.now().date()

    def scrap_incidents(self, id_stf: int) -> None:
        """Extract incidents from search pages and write to the database."""
        logging.info(f"Searching id {id_stf}")
        try:
            search_html: lxml.html.HtmlElement = requester2(
                params.search_url.format(num=id_stf))
        except lxml.etree.ParserError:
            raise Exception(f"Invalid id_stf: {id_stf}.")
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
                # Postgres formats this date string automatically
                data_protocolo: str = item.xpath(
                    "./td[position()=3]/text()")[0]

                meio: str = item.xpath("./td[position()=4]/text()")[0]
                if meio == "Físico":
                    meio_id: int = 1
                elif meio == "Eletrônico":
                    meio_id = 2
                else:
                    raise ValueError(f"Unknown 'meio':{meio}")

                tipo: str = item.xpath("./td[position()=5]/text()")[0]
                if tipo == "Público":
                    tipo_id: int = 1
                elif tipo == "Segredo de Justiça":
                    tipo_id = 2
                elif tipo == "Sigiloso":
                    tipo_id = 3
                else:
                    raise ValueError(f"Unknown 'tipo':{tipo}")

                # Scrap log table
                curs.execute(params.sql_scrap_log_insert,
                             (classe_processo_sigla, id_stf, self.now))
                conn.commit()

                # Data table
                curs.execute(params.sql_stf_data_insert_min, (
                    incidente, numero_unico, id_stf, classe_processo_sigla,
                    data_protocolo, meio_id, tipo_id, self.now))
                conn.commit()

    def calc_start(self, mode: Literal["min", "max", "code"]) -> int:
        """Calculate starting id."""
        if mode == 'full':
            # Start from the beginning
            return 1

        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            if mode == "max":
                curs.execute(params.sql_scrap_log_select_highest)
            elif mode == "min":
                curs.execute(params.sql_scrap_log_select_lowest)
            elif mode == "code":
                curs.execute(params.sql_scrap_log_select_code, (self.code,))

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
                "'sigla' parameter must not be None on 'code' mode.")

        start: int = self.calc_start(mode)
        ids = range(start, start+self.step)
        with ThreadPoolExecutor(max_workers=24) as exec:
            futures = (exec.submit(self.scrap_incidents, id)
                       for id in ids)
            for future in as_completed(futures):
                future.result()

        after_update: int = self.calc_start(mode)
        if after_update == start:
            # No ids found within range
            logging.info("No new ids found in current id range. Done.")
            return False
        else:
            return True


class ProcessScraper:
    """Scrap processes data."""

    def __init__(self, db_params: dict = None):
        """Initialize state, test ``stf_data`` table."""
        self.numero_unico: str = ""
        self.id_stf: int = 0
        self.incidente: int = 0
        self.classe_processo_sigla: str = ""
        self.data_protocolo: date = datetime(1400, 1, 1).date()
        self.meio_id: int = 0
        self.tipo_id: int = 0
        self.classe_processo: str = ""
        self.partes: List[Tuple[str, str]] = []
        self.assuntos: List[str] = []
        self.orgao_origem: str = ""
        self.origem: str = ""
        self.numeros_origem: List[str] = []
        self.scrap_date: date = datetime.now().date()

        if db_params:
            self.db_params: dict = db_params
        else:
            self.db_params = config()

        db_testing("stf_data", params.sql_stf_data_create, self.db_params)

    def decoder(self, string: str) -> str:
        """Decode from utf-8."""
        return string.encode("iso-8859-1").decode("utf-8")

    def _parse_process(self) -> None:
        """Parse 'process' HTML."""
        # Dados gerais
        processo_html: lxml.html.HtmlElement = requester(
            params.process_url.format(incidente=self.incidente))

        self.classe_processo_sigla, self.id_stf = processo_html.xpath(
            "//input[@id='classe-numero-processo']/@value"
        )[0].split(" ")

        # overwrite empty ids
        if self.id_stf == "":
            self.id_stf = 0

        self.numero_unico = (
            processo_html.xpath("//div[@class='processo-rotulo']/text()")[0]
            .replace("Número Único: ", "").replace("-", "").replace(".", ""))
        if self.numero_unico == "Sem número único":
            self.numero_unico = "0"

        meio_tipo_div: lxml.html.HtmlElement = processo_html.xpath(
            "//div[contains(@class, 'processo-titulo')]/div")[0]
        meio: str = meio_tipo_div.xpath("./span[position()=1]/text()")[0]
        if "Eletrônico" in meio:
            self.meio_id = 1
        elif "Físico" in meio:
            self.meio_id = 2
        else:
            raise ValueError(f"Unexpected 'meio' value: {meio}.")

        tipo: str = meio_tipo_div.xpath("./span[position()=2]/text()")[0]
        if tipo == "Público":
            self.tipo_id = 1
        elif tipo == "Segredo de Justiça":
            self.tipo_id = 2
        elif tipo == "Sigiloso":
            self.tipo_id = 3
        else:
            raise ValueError(f"Unexpected 'tipo' value: {tipo}.")

        try:
            self.classe_processo = processo_html.xpath(
                "//div[@class='card-processo']/div/div[contains(@class, 'processo-classe')]/text()")[0]
        except IndexError:
            self.classe_processo = ""

    def _parse_parts(self) -> None:
        """Parse 'parts' HTML."""
        # Partes do processo
        partes_html: lxml.html.HtmlElement = requester(
            params.parties_url.format(incidente=self.incidente))
        partes_list: List[lxml.html.HtmlElement] = partes_html.xpath(
            "//div[@id='todas-partes']/div[contains(@class, 'processo-partes')]"
        )
        if len(partes_list):
            for parte in partes_list:
                tipo: str = self.decoder(parte.xpath(
                    "./div[@class='detalhe-parte']/text()")[0])
                nome: str = self.decoder(parte.xpath(
                    "./div[@class='nome-parte']/text()")[0])
                self.partes.append((tipo, nome))

    def _parse_incident(self) -> None:
        """Parse 'incident' HTML."""
        # Detalhes do processo
        detalhes_html: lxml.html.HtmlElement = requester(
            params.details_url.format(incidente=self.incidente))
        assuntos: List[lxml.html.HtmlElement] = detalhes_html.xpath(
            "//ul[@style='list-style:none;']/li")
        if len(assuntos):
            for assunto in assuntos:
                assunto = assunto.xpath("text()")[0]
                assunto_items: List[str] = assunto \
                    .replace("||", "|").split("|")
                clean_assunto: str = "; ".join(assunto.strip()
                                               for assunto in assunto_items)
                self.assuntos.append(self.decoder(clean_assunto))

        # A positional approach could be used but the tags positions might not
        # be the same across all processes.
        # Looks for tags that contain the 'Origem:' text
        for item in detalhes_html.xpath("//*[text()[contains(.,':')]]"):
            # If it is an exact match
            if self.decoder(item.xpath("./text()")[0]
                            .strip()) == "Data de Protocolo:":
                # Get next sibiling's text
                raw_date = self.decoder(
                    item.getnext().xpath("text()")[0].strip())
                if raw_date != "":
                    self.data_protocolo = datetime \
                        .strptime(raw_date, "%d/%m/%Y").date()
            if self.decoder(item.xpath("./text()")[0]
                            .strip()) == "Órgão de Origem:":
                self.orgao_origem = self.decoder(
                    item.getnext().xpath("text()")[0].strip())
            if self.decoder(item.xpath("./text()")[0].strip()) == "Origem:":
                self.origem = self.decoder(
                    item.getnext().xpath("text()")[0].strip())
            if self.decoder(item.xpath("./text()")[0]
                            .strip()) == "Número de Origem:":
                nums = self.decoder(item.getnext().xpath("text()")[0])
                self.numeros_origem = re.sub(r"[\n\t\s]*", "", nums).split(",")

    def scrap_process(self, incidente: tuple) -> None:
        """Scrap a process and save parsed data."""
        self.incidente = incidente[0]
        logging.info(f"Saving details from {self.incidente}")

        self._parse_process()
        self._parse_parts()
        self._parse_incident()

        # Lists must be converted to strings before writing to DB for now
        payload = (self.incidente, self.numero_unico, self.id_stf,
                   self.classe_processo_sigla, self.data_protocolo,
                   self.meio_id, self.tipo_id, self.classe_processo,
                   str(self.partes), str(self.assuntos), self.orgao_origem,
                   self.origem, str(self.numeros_origem), self.scrap_date)

        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(params.sql_stf_data_insert_row, payload)
            curs.execute(params.sql_temp_incidents_remove, incidente)
            conn.commit()

    def retrive_incidents(self) -> Generator[int, None, None]:
        """DB."""
        with pg.connect(**self.db_params) as conn, conn.cursor() as curs:
            curs.execute(params.sql_temp_incidents_read)
            yield from curs

    def start(self) -> bool:
        """Scrap from incidents logs."""
        with ThreadPoolExecutor(max_workers=24) as exec:
            futures = (exec.submit(self.scrap_process, i)
                       for i in self.retrive_incidents())
            for future in as_completed(futures):
                future.result()

        return True


if __name__ == "__main__":
    search_scraper = SearchScraper()
    status = True
    # Modes: 'max', 'min', 'code'
    while status:
        status = search_scraper.start(mode="max")

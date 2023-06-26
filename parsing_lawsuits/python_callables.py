
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from random import randint
from tempfile import tempdir
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import pandas as pd
import selenium.webdriver.support.expected_conditions as EC
import undetected_chromedriver as uc
from pypdf import PdfReader
from selenium.common.exceptions import (ElementNotInteractableException,
                                        InvalidSelectorException,
                                        WebDriverException)
from selenium.webdriver.remote.webdriver import By
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm

MIN_SLEEP = 5
MAX_SLEEP = 7

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Referer': 'https://kad.arbitr.ru/Document/Pdf/6458e816-341e-467a-96d7-fa997fef10ce/2503801c-350e-4437-bc75-c92f2194ad94/A19-4768-2023_20230313_Opredelenie.pdf',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
}


@dataclass
class ElectronicCase:
    """Ссылки на электронные дела
    """
    url_case: str
    date: datetime
    path: str = field(default="")
    name_pdf: str = field(default="")


@dataclass
class CourtCase:
    """Судебное дело
    """
    name_court: str
    url_court: str
    plaintiff: str
    respondent: str
    name_company: str
    electronic_cases: Optional[List[ElectronicCase]
                               ] = field(default_factory=list)


def get_lawsuits(name: str, start_url: str = "https://kad.arbitr.ru/") -> List[CourtCase]:

    driver = uc.Chrome(headless=True)
    driver._web_element_cls = uc.UCWebElement
    driver.get(start_url)

    driver.find_elements(
        By.XPATH, '//*[@id="sug-participants"]/div/textarea')[0].click()
    driver.find_elements(
        By.XPATH, '//*[@id="sug-participants"]/div/textarea')[0].send_keys(name)
    driver.find_elements(
        By.XPATH, '//*[@id="b-form-submit"]/div/button')[0].click()

    court_cases: List[CourtCase] = []
    try:
        while True:

            time.sleep(randint(MIN_SLEEP, MAX_SLEEP))

            table = driver.find_elements(By.XPATH, '//*[@id="table"]')[0]
            table_content = driver.find_element(
                By.XPATH, '//*[@id="b-cases"]/tbody')

            table_rows = table_content.find_elements(
                By.XPATH, '//*[@id="b-cases"]/tbody/tr')
            for item_tr in table_rows:

                url = item_tr.find_element(
                    By.CLASS_NAME,   'num').find_element(By.TAG_NAME, "a").get_attribute("href")
                name_court = item_tr.find_element(
                    By.CLASS_NAME, 'num').text

                plaintiff = item_tr.find_element(
                    By.CLASS_NAME, "plaintiff").text
                respondent = item_tr.find_element(
                    By.CLASS_NAME, "respondent").text
                tmp_court_case = CourtCase(
                    name_court, url, plaintiff, respondent, name)
                court_cases.append(tmp_court_case)
                del item_tr
            driver.find_elements(
                By.XPATH, '//*[@id="pages"]/li[@class="rarr"]')[0].click()
    except IndexError as _:
        logging.info("successed")
    except InvalidSelectorException as _:
        logging.info("success")
    except ElementNotInteractableException as _:
        logging.info("success")
    driver.close()
    return court_cases


def get_electronic_cases(cases: List[CourtCase]) -> List:
    options = uc.ChromeOptions()

    driver = uc.Chrome(headless=True)

    for case in tqdm(cases):

        driver.get(case.url_court)
        time.sleep(randint(MIN_SLEEP, MAX_SLEEP))
        driver.find_elements(
            By.XPATH, '//*[@class="b-case-chrono-button-text"]')[2].click()
        time.sleep(randint(MIN_SLEEP, MIN_SLEEP))
        elements = driver.find_elements(
            By.XPATH, '//*[@class="b-case-chrono-content"]/ul/li')
        pdf_urls = []
        tmp_electronic_cases = []
        for element in elements:
            pdf_url = element.find_element(
                By.XPATH, './/a').get_attribute("href")
            pdf_date = element.find_element(
                By.CLASS_NAME, "b-case-chrono-ed-item-date").text

            dt = datetime.strptime(pdf_date, '%d.%m.%Y')
            tmp_electronic_case = ElectronicCase(pdf_url, dt)
            tmp_electronic_cases.append(tmp_electronic_case)
            pdf_urls.append(pdf_url)

        path_dir = f"{os.getcwd()}/pdf/{case.name_company}/{case.name_court}"
        if pdf_urls:
            options = uc.ChromeOptions()
            options.add_experimental_option('prefs', {
                "download.default_directory": path_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True
            })
            especially_driver = uc.Chrome(options=options, headless=True)
            especially_driver.implicitly_wait(10)
            for ecase in tmp_electronic_cases:
                especially_driver.get(ecase.url_case)
                name_pdf = pdf_url.split('/')[-1]
                ecase.name_pdf = name_pdf
                ecase.path = path_dir
                time.sleep(randint(MIN_SLEEP+2, MAX_SLEEP+2))
            especially_driver.close()
        case.electronic_cases = tmp_electronic_cases

    driver.close()
    return cases


def export_to_csv(cases: List[CourtCase], name_company: str) -> None:
    to_export = [asdict(case) for case in cases]
    result = []
    for row in to_export:
        tmp_dict = {**row}
        tmp_dict.pop("electronic_cases")
        for sub_row in row["electronic_cases"]:
            tmp_dict = {**tmp_dict, **sub_row}
            result.append(tmp_dict)
    df = pd.DataFrame(result)
    df.to_csv(f"{name_company}.csv", index=False)


def read_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def preprocessing_data(df: pd.DataFrame):
    """Предобработка собранных данных для дальнейшего подсчёта оценок

    Args:
        df (pd.DataFrame): Плоские данные структуры CourtCase
    """
    def is_respondent(row: Dict[str, Any]) -> bool:
        """Компания является ответчиком

        Args:
            row (Dict[str, Any]): Запись о судебном документе

        Returns:
            bool: True/False
        """
        name_company = row["name_company"].lower()
        respondent = row["respondent"].lower()
        return name_company in respondent

    def is_apply(row: Dict[str, Any]) -> bool:
        """Фильтрация по истцу и ответчику. 
        Если нет упоминания о компании, то это некорректная запись

        Args:
            row (Dict[str, Any]): Запись о судебном документе

        Returns:
            bool: True/False
        """
        name_company = row["name_company"].lower()
        respondent = row["respondent"].lower()
        plaintiff = row["plaintiff"].lower()
        return (name_company in respondent) or (name_company in plaintiff)

    def is_win(text: str, row: Dict[str, Any]) -> bool:
        """Дело выиграно или в ином статусе

        Args:
            text (str): Текст дела
            row (Dict[str, Any]): Запись о судебном документе

        Returns:
            bool: True/False
        """
        raw_win = re.search("удовлетворить", text)
        if row["is_respondent"] and raw_win:
            return False

        if row["is_respondent"] == False and raw_win:
            return True
        return False

    def court_value(text: str, row: Dict[str, Any]) -> float:
        """Оценка текущего состояния дела

        Args:
            text (str): Текст дела
            row (Dict[str, Any]): Запись о судебном документе

        Returns:
            float: _description_
        """
        RESPONDENT_LOSE = 0
        RESPONDENT_WIN = 0.375
        RESPONDENT_STOP = 0.25
        RESPONDENT_CONSIDERATION = 0.125

        PLANTIFF_LOSE = 0.625
        PLANTIFF_WIN = 1
        PLANTIFF_STOP = 0.75
        PLANTIFF_CONSIDERATION = 0.875

        is_respondent = row["is_respondent"]
        if is_respondent:
            if row["is_win"]:
                return RESPONDENT_WIN
            is_stop = bool(re.search("прекратить", text))
            if is_stop:
                return RESPONDENT_STOP
            is_stop = bool(re.search("отказать", text))
            if is_stop:
                return RESPONDENT_STOP
            is_stop = bool(re.search("остановить", text))
            if is_stop:
                return RESPONDENT_STOP
            is_consideration = bool(re.search("рассмотреть", text))
            if is_consideration:
                return RESPONDENT_CONSIDERATION
            return RESPONDENT_LOSE

        else:
            if row["is_win"]:
                return PLANTIFF_WIN
            is_stop = bool(re.search("прекратить", text))
            if is_stop:
                return PLANTIFF_STOP
            is_stop = bool(re.search("отказать", text))
            if is_stop:
                return PLANTIFF_STOP
            is_stop = bool(re.search("остановить", text))
            if is_stop:
                return PLANTIFF_STOP
            is_consideration = bool(re.search("рассмотреть", text))
            if is_consideration:
                return PLANTIFF_CONSIDERATION
            return PLANTIFF_LOSE

    rows = df.to_dict("records")

    result_rows = []

    for row in tqdm(rows):
        row["is_apply"] = is_apply(row)

        if row["is_apply"]:
            path_to_pdf = f"{row['path']}/{row['name_pdf']}"
            reader = PdfReader(path_to_pdf)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            text = text.lower()

            flag_respondent = is_respondent(row)

            row["is_respondent"] = flag_respondent

            if flag_respondent:
                raw_debt = re.search("[\s*,*\d*\s*]+руб", text)
                if raw_debt:
                    debt = float(raw_debt.group(0).replace(
                        ' ', '').replace('руб', '').replace(',', '.'))
                else:
                    debt = 0.0
            else:
                debt = 0.0
            row["debt"] = debt

            row["is_win"] = is_win(text, row)
            row["court_value"] = court_value(text, row)
            result_rows.append(row)
    return result_rows


def calculate_debts(debt: float, auth_capital: float, as_capital: float):
    pass

import base64
import io
import logging
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from random import randint
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import numpy as np
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
class LawsuitDocument:
    """Ссылки на электронные дела
    """
    url_case: str
    date: datetime
    path: str = field(default="")
    name_pdf: str = field(default="")
    data: str = field(default="")


@dataclass
class Lawsuit:
    """Судебное дело
    """
    name_court: str
    url_court: str
    plaintiff: str
    respondent: str
    name_company: str
    electronic_cases: List[LawsuitDocument] = field(default=list)


@dataclass
class FlatLawsuit:
    """Плоские судебные дела
    """
    url_case: str
    date: datetime
    name_court: str
    url_court: str
    plaintiff: str
    respondent: str
    name_company: str
    path: str = field(default="")
    name_pdf: str = field(default="")
    data: str = field(default="")
    is_respondent: bool = field(default=False)
    is_win: bool = field(default=False)
    is_apply: bool = field(default=True)
    debt: float = field(default=0.0)
    court_value: float = field(default=0.0)


def get_lawsuits(name: str, start_url: str = "https://kad.arbitr.ru/") -> List[Lawsuit]:
    """По наименованию компании получить список электронных дел

    Args:
        name (str): Наименование компании
        start_url (_type_, optional): Стартовая ссылка. Defaults to "https://kad.arbitr.ru/".

    Returns:
        List[CourtCase]: Список электронных дел
    """

    driver = uc.Chrome(headless=True)
    driver._web_element_cls = uc.UCWebElement
    driver.get(start_url)

    driver.find_elements(
        By.XPATH, '//*[@id="sug-participants"]/div/textarea')[0].click()
    driver.find_elements(
        By.XPATH, '//*[@id="sug-participants"]/div/textarea')[0].send_keys(name)
    driver.find_elements(
        By.XPATH, '//*[@id="b-form-submit"]/div/button')[0].click()

    court_cases: List[Lawsuit] = []
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
                tmp_court_case = Lawsuit(
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


def get_electronic_cases(cases: List[Lawsuit], deep: int = -1) -> List:
    """Парсит электронные документы. Достает pdf файлы с делами.
    Сохраняет их локально в папку

    Args:
        cases (List[CourtCase]): Электронные дела

    Returns:
        List: Список электронных дел
    """
    options = uc.ChromeOptions()
    if deep < 0:
        deep = len(cases)
    driver = uc.Chrome(headless=True)

    for case in tqdm(cases[:deep], "scraping lawsuits"):
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
            logging.info(f"pdf url:{pdf_url}")
            pdf_date = element.find_element(
                By.CLASS_NAME, "b-case-chrono-ed-item-date").text
            dt = datetime.strptime(pdf_date, '%d.%m.%Y')
            logging.info(f"pdf date:{dt}")
            tmp_electronic_case = LawsuitDocument(pdf_url, dt)
            tmp_electronic_case.name_pdf = pdf_url.split('/')[-1]
            logging.info(f"name pdf:{tmp_electronic_case.name_pdf}")
            tmp_electronic_cases.append(tmp_electronic_case)
            pdf_urls.append(pdf_url)
            logging.info(f"{tmp_electronic_case.name_pdf} sent to queued")

        if pdf_urls:
            with tempfile.TemporaryDirectory() as tmpdirname:
                path_dir = f"{tmpdirname}/{case.name_company}"
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
                    logging.info(f"get {ecase.url_case}")
                    especially_driver.get(ecase.url_case)
                    ecase.path = path_dir
                    time.sleep(randint(MIN_SLEEP+2, MAX_SLEEP+2))
                    full_path = f"{path_dir}/{ecase.name_pdf}"
                    logging.info(f"saving {ecase.name_pdf} to {full_path}")
                    with open(full_path, "rb") as f:
                        pdf_data = f.read()
                        encoded = base64.b64encode(pdf_data)
                        del pdf_data
                        ecase.data = encoded
                especially_driver.close()

        case.electronic_cases = tmp_electronic_cases
    driver.close()
    return cases[:deep]


def preprocessing_data(lawsuits: List[Lawsuit]) -> List[FlatLawsuit]:
    """Обработка собранных данных для дальнейшего подсчёта оценок

    Args:
        df (pd.DataFrame): Плоские данные структуры CourtCase
    """
    def is_respondent(flat_lawsuit: FlatLawsuit) -> bool:
        """Компания является ответчиком

        Args:
            flat_lawsuit (Dict[str, Any]): Запись о судебном документе

        Returns:
            bool: True/False
        """
        name_company = flat_lawsuit.name_company.lower()
        respondent = flat_lawsuit.respondent.lower()
        return name_company in respondent

    def is_apply(flat_lawsuit: FlatLawsuit) -> bool:
        """Фильтрация по истцу и ответчику. 
        Если нет упоминания о компании, то это некорректная запись

        Args:
            flat_lawsuit (FlatLawsuit): Запись о судебном документе

        Returns:
            bool: True/False
        """
        name_company = flat_lawsuit.name_company.lower()
        respondent = flat_lawsuit.respondent.lower()
        plaintiff = flat_lawsuit.plaintiff.lower()
        return (name_company in respondent) or (name_company in plaintiff)

    def is_win(text: str, flat_lawsuit: FlatLawsuit) -> bool:
        """Дело выиграно или в ином статусе

        Args:
            text (str): Текст дела
            flat_lawsuit (FlatLawsuit): Запись о судебном документе

        Returns:
            bool: True/False
        """
        raw_win = re.search("удовлетворить", text)
        if flat_lawsuit.is_respondent and raw_win:
            return False

        if flat_lawsuit.is_respondent == False and raw_win:
            return True
        return False

    def court_value(text: str, flat_lawsuit: FlatLawsuit) -> float:
        """Оценка текущего состояния дела

        Args:
            text (str): Текст дела
            flat_lawsuit (FlatLawsuit): Запись о судебном документе

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

        is_respondent = flat_lawsuit.is_respondent
        if is_respondent:
            if flat_lawsuit.is_win:
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
            if flat_lawsuit.is_win:
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

    def flatten_lawsuits(lawsuits: List[Lawsuit]) -> List[FlatLawsuit]:
        """Преобразование списка судебных дел в плоские данные

        Args:
            lawsuits (List[CourtCase]): Список электронных дел

        Returns:
            List[Dict[str,Any]]: Плоские данные
        """
        lawsuits_dicts = [asdict(case) for case in lawsuits]
        flatten_lawsuits = []
        for row in lawsuits_dicts:
            tmp_dict = {**row}
            tmp_dict.pop("electronic_cases")
            for sub_row in row["electronic_cases"]:
                tmp_dict = {**tmp_dict, **sub_row}
                flatten_lawsuits.append(FlatLawsuit(**tmp_dict))
        return flatten_lawsuits

    result_lawsuits = []

    flat_lawsuits = flatten_lawsuits(lawsuits)

    for flat_lawsuit in tqdm(flat_lawsuits, "precessing lawsuits"):
        flat_lawsuit.is_apply = is_apply(flat_lawsuit)

        if flat_lawsuit.is_apply:
            decoded = base64.b64decode(flat_lawsuit.data)
            reader = PdfReader(io.BytesIO(decoded))
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            text = text.lower()

            flag_respondent = is_respondent(flat_lawsuit)

            flat_lawsuit.is_respondent = flag_respondent

            if flag_respondent:
                raw_debt = re.search("[\s*,*\d*\s*]+руб", text)
                if raw_debt:
                    debt = float(raw_debt.group(0).replace(
                        ' ', '').replace('руб', '').replace('\n', '').replace(',', '.'))
                else:
                    debt = 0.0
            else:
                debt = 0.0
            flat_lawsuit.debt = debt

            flat_lawsuit.is_win = is_win(text, flat_lawsuit)
            flat_lawsuit.court_value = court_value(text, flat_lawsuit)
            result_lawsuits.append(flat_lawsuit)
    return result_lawsuits


def calculate_grades(flat_lawsuits: List[FlatLawsuit],
                     AuthC: float,
                     AsC: float,
                     w1=1, w2=1, w3=1, w4=1, w5=1) -> List[Dict[str, Any]]:
    """Подсчёт судебного имиджа

    Args:
        flat_lawsuits (List[FlatLawsuit]): Обработанные судебные иски
        AuthC (float): Уставной капитал
        AsC (float): Активы
        w1 (int, optional): Коэффициент a1. Defaults to 1.
        w2 (int, optional): Коэффициент a2. Defaults to 1.
        w3 (int, optional): Коэффициент a3. Defaults to 1.
        w4 (int, optional): Коэффициент a4. Defaults to 1.
        w5 (int, optional): Коэффициент a5. Defaults to 1.

    Returns:
        List[Dict[str, Any]]: _description_
    """
    df = pd.DataFrame([asdict(lawsuit) for lawsuit in flat_lawsuits])
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df_group = df.groupby([df.year, df.month]).agg(
        {"debt": "sum", "url_case": "count", "is_respondent": "sum", "is_win": "sum", "court_value": "mean"})
    del df
    df_group = df_group.reset_index()
    df_group["date"] = pd.to_datetime(df_group.year.astype(
        str) + '/' + df_group.month.astype(str) + '/01')
    df_group = df_group[df_group["date"].dt.year >= 2022]
    df_group.rename(columns={"url_case": "count"}, inplace=True)

    df_group["a1"] = (df_group["debt"]/AuthC + df_group["debt"]/AsC)
    df_group.replace([np.inf, -np.inf], 0, inplace=True)

    a_2 = []
    for _, row in df_group.iterrows():
        tmp_dict = row.to_dict()
        tmp_date = tmp_dict["date"]
        tmp_df = df_group[df_group["date"] <= tmp_date]
        tmp_a2 = tmp_df["count"].mean() / tmp_df["count"].std()
        a_2.append(tmp_a2)
    df_group["a2"] = a_2
    df_group.replace([np.inf, -np.inf, np.nan], 3.33, inplace=True)

    a_3 = []
    for _, row in df_group.iterrows():
        tmp_dict = row.to_dict()
        tmp_date = tmp_dict["date"]
        tmp_df = df_group[df_group["date"] <= tmp_date]
        tmp_a3 = tmp_df["is_respondent"].sum()/tmp_df["count"].sum()
        a_3.append(tmp_a3)
    df_group["a3"] = a_3
    df_group.replace([np.inf, -np.inf, np.nan], 3.33, inplace=True)

    a_4 = []
    for _, row in df_group.iterrows():
        tmp_dict = row.to_dict()
        tmp_date = tmp_dict["date"]
        tmp_df = df_group[df_group["date"] <= tmp_date]
        tmp_a4 = tmp_df["is_win"].sum()/tmp_df["count"].sum()
        a_4.append(tmp_a4)
    df_group["a4"] = a_4
    df_group.replace([np.inf, -np.inf, np.nan], 3.33, inplace=True)

    df_group["a5"] = df_group["court_value"].copy()
    w1 = w2 = w3 = w4 = w5 = 1
    df_group['grade'] = np.sqrt(w1*(df_group['a1']**2)+w2*(df_group['a2']**2)+w3 *
                                (df_group['a3']**2)+w4*(df_group['a4']**2)+w5*(df_group['a5']**2))
    return df_group.to_dict()

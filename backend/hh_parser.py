import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Any

# Логируем и в файл, и в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ID региона Челябинская область и город Челябинск
REGION_ID = 113
CITY_NAME = 'Челябинск'
CITY_AREA_ID: int = None


def create_session(retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def get_city_area_id(session: requests.Session) -> int:
    """
    Запрашивает через API HH деревья регионов и возвращает ID города Челябинск.
    """
    global CITY_AREA_ID
    if CITY_AREA_ID:
        return CITY_AREA_ID
    try:
        resp = session.get(
            f'https://api.hh.ru/areas/{REGION_ID}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        for area in data.get('areas', []):
            if area.get('name') == CITY_NAME:
                CITY_AREA_ID = int(area.get('id'))
                logging.info(f"Найден ID города {CITY_NAME}: {CITY_AREA_ID}")
                return CITY_AREA_ID
        logging.warning(f"Город {CITY_NAME} не найден в регионе {REGION_ID}, используем регион")
    except Exception as e:
        logging.error(f"Ошибка при получении ID города: {e}")
    return REGION_ID


def fetch_vacancies(max_pages: int = 5) -> List[Dict[str, Any]]:
    """
    Получение IT-вакансий из HH.ru за последние 7 дней строго из Челябинска.
    max_pages — максимальное число страниц (по 50 записей) для каждого запроса.
    """
    days = 7
    logging.info(f"Начало парсинга HH.ru за последние {days} дней для IT-вакансий в Челябинске")
    session = create_session()
    city_area = get_city_area_id(session)

    base_params = {
        'area': city_area,
        'per_page': 50,
        'date_from': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
        'order_by': 'publication_time',
        'only_with_salary': False,
        'experience': ['noExperience', 'between1And3']
    }
    queries = [
        "(программист OR разработчик) AND (стажер OR junior OR начинающий)",
        "1С AND (стажер OR junior OR без опыта)",
        "(devops OR sre) AND (стажер OR junior)",
        "(data engineer OR etl) AND (стажер OR junior)",
        "(тестировщик OR qa) AND (стажер OR junior)",
        "(системный администратор OR it-специалист) AND (стажер OR junior)"
    ]

    all_vacancies: List[Dict[str, Any]] = []
    for query in queries:
        params = {**base_params, 'text': query}
        logging.info(f"Запрос: {query} — до {max_pages} страниц")

        for page in range(max_pages):
            try:
                resp = session.get(
                    'https://api.hh.ru/vacancies',
                    params={**params, 'page': page},
                    headers={'User-Agent': 'Mozilla/5.0'},
                    timeout=10
                )
                if resp.status_code != 200:
                    logging.warning(f"Страница {page+1} вернула {resp.status_code} для запроса {query}")
                    break
                items = resp.json().get('items', [])
                logging.info(f"{query}: страница {page+1}, вакансий {len(items)}")
                if not items:
                    break
                all_vacancies.extend(items)
            except Exception as e:
                logging.error(f"Ошибка на странице {page+1} для {query}: {e}")
                break
            time.sleep(1)

    logging.info(f"Всего получено вакансий (до фильтрации): {len(all_vacancies)}")
    return all_vacancies


def is_it_vacancy(title: str, description: str) -> bool:
    lower_title = title.lower()
    lower_desc = description.lower()
    exclude = [
        'менеджер', 'маркетинг', 'торгов', 'кофе', 'помощник',
        'бухгалтер', 'юрист', 'рекрутер', 'ассистент', 'консультант',
        'преподовател', 'оператор', 'директор', 'руководитель',
        'координатор', 'логист', 'продаж', 'закупк', 'персон',
        'кадр', 'hr', 'офис', 'секретар', 'администратор',
        'финанс', 'банк', 'кредит', 'аудит', 'экономист',
        'медицинск', 'здравоохранен', 'социолог', 'психолог'
    ]
    it_keys = [
        'программист', 'разработчик', 'developer', 'engineer',
        'backend', 'frontend', 'fullstack', 'web', '1с',
        'data engineer', 'etl', 'dwh', 'data scientist', 'ml', 'ai',
        'qa', 'тестировщик', 'sre', 'devops', 'cloud', 'security',
        'android', 'ios', 'mobile'
    ]
    tech = [
        'python', 'java', 'c#', 'sql', 'javascript', 'php', 'git',
        'docker', 'kubernetes', 'linux', 'bash', 'django', 'flask',
        'react', 'vue', 'spring', 'net', 'postgres', 'mysql', 'mongodb'
    ]

    if any(ex in lower_title for ex in exclude):
        return False
    if not any(key in lower_title for key in it_keys):
        return False
    if not any(skill in lower_desc for skill in tech):
        return False
    return True


def format_salary(salary: Dict[str, Any]) -> str:
    if not salary:
        return 'не указана'
    parts = []
    if salary.get('from'):
        parts.append(f"от {salary['from']}")
    if salary.get('to'):
        parts.append(f"до {salary['to']}")
    curr = salary.get('currency', '')
    if curr == 'RUR': curr = 'руб.'
    return ' '.join(parts) + (f" {curr}" if curr else '')


def clean_description(desc: str) -> str:
    import re
    text = re.sub('<[^<]+?>', '', desc)
    text = ' '.join(text.split())
    return text[:500] + '...' if len(text) > 500 else text


def categorize_vacancy(title: str, description: str) -> str:
    tl = title.lower()
    if 'стажер' in tl or 'intern' in tl or 'практикант' in tl:
        return 'internship'
    if 'junior' in tl or 'младший' in tl:
        return 'junior'
    if '1с' in tl or '1c' in tl:
        return '1c'
    return 'development'


def parse_vacancies() -> List[Dict[str, Any]]:
    raw = fetch_vacancies(max_pages=5)
    parsed: List[Dict[str, Any]] = []
    for item in raw:
        title = item.get('name', '').strip()
        snippet = item.get('snippet', {}) or {}
        responsibility = snippet.get('responsibility') or ''
        requirement = snippet.get('requirement') or ''
        desc = f"{responsibility} {requirement}".strip()

        if not is_it_vacancy(title, desc):
            continue
        parsed.append({
            'title': title,
            'company': item.get('employer', {}).get('name', 'не указана'),
            'salary': format_salary(item.get('salary', {})),
            'experience': item.get('experience', {}).get('name', 'не указан'),
            'url': item.get('alternate_url', '#'),
            'description': clean_description(desc),
            'type': categorize_vacancy(title, desc),
            'published_at': item.get('published_at', '')
        })
    logging.info(f"Успешно отфильтровано IT-вакансий: {len(parsed)}")
    return parsed

if __name__ == '__main__':
    for v in parse_vacancies()[:5]:
        print(v)



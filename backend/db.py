import sqlite3
from datetime import datetime
from werkzeug.security import check_password_hash

def init_db():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()

    # Таблица вакансий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            salary TEXT,
            experience TEXT,
            url TEXT UNIQUE,
            description TEXT,
            published_at TEXT
        )
    ''')

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            group_number TEXT,
            email TEXT,
            phone TEXT,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL,
            last_login TEXT,
            UNIQUE(full_name, user_type)
        )
    ''')

    # Таблица избранных вакансий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vacancy_id INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(vacancy_id) REFERENCES vacancies(id),
            UNIQUE(user_id, vacancy_id)
        )
    ''')

    # Таблица трудоустройств
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vacancy_id INTEGER NOT NULL,
            employed_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(vacancy_id) REFERENCES vacancies(id),
            UNIQUE(user_id)
        )
    ''')

    conn.commit()
    conn.close()


def add_vacancies(vacancies):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    for v in vacancies:
        try:
            cursor.execute('''
                INSERT INTO vacancies (title, company, salary, experience, url, description, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
            v['title'], v['company'], v['salary'], v['experience'], v['url'], v['description'], v['published_at']))
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()


def get_vacancies():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, company, salary, experience, url, published_at FROM vacancies ORDER BY published_at DESC')
    vacancies = cursor.fetchall()
    conn.close()
    return [{
        'id': v[0],
        'title': v[1],
        'company': v[2],
        'salary': v[3] if v[3] else 'не указана',
        'experience': v[4] if v[4] else 'не указан',
        'url': v[5],
        'published_at': v[6] if v[6] else 'не указана'
    } for v in vacancies]


def get_vacancy_by_id(vacancy_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, company, salary, experience, url, published_at FROM vacancies WHERE id = ?',
                   (vacancy_id,))
    v = cursor.fetchone()
    conn.close()
    if v:
        return {
            'id': v[0],
            'title': v[1],
            'company': v[2],
            'salary': v[3] if v[3] else 'не указана',
            'experience': v[4] if v[4] else 'не указан',
            'url': v[5],
            'published_at': v[6]
        }
    return None


# Функции для работы с пользователями
def add_user(full_name, group_number, password, user_type):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (full_name, group_number, password, user_type, last_login)
            VALUES (?, ?, ?, ?, ?)
        ''', (full_name, group_number, password, user_type, datetime.now().isoformat()))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_all_students_with_last_login():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT full_name, group_number, last_login 
        FROM users 
        WHERE user_type = 'student'
        ORDER BY group_number, full_name
    ''')
    students = cursor.fetchall()
    conn.close()
    return [{
        'full_name': s[0],
        'group_number': s[1],
        'last_login': s[2]
    } for s in students]

def get_user_by_id(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, full_name, group_number, user_type 
        FROM users 
        WHERE id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            'id': user[0],
            'full_name': user[1],
            'group_number': user[2],
            'user_type': user[3]
        }
    return None

def get_user(full_name, password, user_type):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, full_name, group_number, password, user_type 
        FROM users 
        WHERE full_name = ? AND user_type = ?
    ''', (full_name, user_type))
    user_data = cursor.fetchone()
    conn.close()

    if user_data and check_password_hash(user_data[3], password):
        return {
            'id': user_data[0],
            'full_name': user_data[1],
            'group_number': user_data[2],
            'user_type': user_data[4]
        }
    return None


def update_user_login(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET last_login = ? WHERE id = ?
    ''', (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, full_name, group_number, user_type, last_login 
        FROM users 
        ORDER BY group_number, full_name
    ''')
    users = cursor.fetchall()
    conn.close()
    return [{
        'id': u[0],
        'full_name': u[1],
        'group_number': u[2],
        'user_type': u[3],
        'last_login': u[4]
    } for u in users]


# Функции для работы с избранными вакансиями
def add_favorite(user_id, vacancy_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO favorites (user_id, vacancy_id, added_at) VALUES (?, ?, datetime("now"))',
                      (user_id, vacancy_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_favorite(user_id, vacancy_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM favorites WHERE user_id = ? AND vacancy_id = ?',
                      (user_id, vacancy_id))
        conn.commit()
        return cursor.rowcount > 0  # Возвращает True если удаление прошло успешно
    except sqlite3.Error as e:
        print(f"Ошибка при удалении из избранного: {e}")
        return False
    finally:
        conn.close()


def get_favorites(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.id, v.title, v.company, v.salary, v.url, v.published_at 
        FROM favorites f
        JOIN vacancies v ON f.vacancy_id = v.id
        WHERE f.user_id = ?
        ORDER BY f.added_at DESC
    ''', (user_id,))
    vacancies = cursor.fetchall()
    conn.close()
    return [{
        'id': v[0],
        'title': v[1],
        'company': v[2],
        'salary': v[3],
        'url': v[4],
        'published_at': v[5]
    } for v in vacancies]


def is_favorite(user_id, vacancy_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND vacancy_id = ?', (user_id, vacancy_id))
    result = cursor.fetchone() is not None
    conn.close()
    return result

# Функции для работы с трудоустройством
def set_employment(user_id, vacancy_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM employment WHERE user_id = ?', (user_id,))
        cursor.execute('INSERT INTO employment (user_id, vacancy_id, employed_at) VALUES (?, ?, datetime("now"))',
                      (user_id, vacancy_id))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def remove_employment(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM employment WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def get_employment(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.id, v.title, v.company, v.salary, v.url, v.published_at
        FROM employment e
        JOIN vacancies v ON e.vacancy_id = v.id
        WHERE e.user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'id': result[0],
            'title': result[1],
            'company': result[2],
            'salary': result[3],
            'url': result[4],
            'published_at': result[5]
        }
    return None

def get_all_employments():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.full_name, u.group_number, v.title, v.company, v.url
        FROM employment e
        JOIN users u ON e.user_id = u.id
        JOIN vacancies v ON e.vacancy_id = v.id
        ORDER BY u.group_number, u.full_name
    ''')
    employments = cursor.fetchall()
    conn.close()
    return [{
        'full_name': e[0],
        'group_number': e[1],
        'title': e[2],
        'company': e[3],
        'url': e[4]
    } for e in employments]
import sqlite3

def init_db():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            salary TEXT,
            experience TEXT,
            url TEXT UNIQUE,
            description TEXT
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
                INSERT INTO vacancies (title, company, salary, experience, url, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (v['title'], v['company'], v['salary'], v['experience'], v['url'], v['description']))
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()

def get_vacancies():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title, company, salary, experience, url FROM vacancies')
    vacancies = cursor.fetchall()
    conn.close()
    return [{
        'title': v[0],
        'company': v[1],
        'salary': v[2],
        'experience': v[3],
        'url': v[4]
    } for v in vacancies]

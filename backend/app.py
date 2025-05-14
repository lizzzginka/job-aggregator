from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from hh_parser import parse_vacancies
from db import init_db, add_vacancies, get_vacancies

# Инициализация Flask приложения
app = Flask(__name__)
CORS(app)  # Разрешаем CORS

# Инициализация базы данных
init_db()

# HTML шаблон для отображения вакансий
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Вакансии для студентов ЮУрГУ</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .vacancy { 
            border: 1px solid #ddd; 
            padding: 15px; 
            margin-bottom: 15px;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
        .vacancy-title { 
            font-size: 18px; 
            color: #2c3e50; 
            margin-bottom: 5px;
        }
        .vacancy-company { 
            font-weight: bold; 
            color: #3498db;
        }
        .vacancy-salary { 
            color: #27ae60; 
            font-weight: bold;
        }
        .vacancy-experience { 
            color: #7f8c8d;
        }
        .vacancy-link { 
            display: inline-block; 
            margin-top: 10px; 
            color: #fff;
            background-color: #3498db;
            padding: 5px 10px;
            text-decoration: none;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <h1>IT-вакансии в Челябинске для студентов</h1>
    <p>Найдено вакансий: {{ vacancies|length }}</p>

    {% for v in vacancies %}
    <div class="vacancy">
        <div class="vacancy-title">{{ v.title }}</div>
        <div>
            <span class="vacancy-company">{{ v.company }}</span> • 
            <span class="vacancy-salary">{{ v.salary }}</span> • 
            <span class="vacancy-experience">{{ v.experience }}</span>
        </div>
        <p>{{ v.description }}</p>
        <a href="{{ v.url }}" class="vacancy-link" target="_blank">Открыть на hh.ru</a>
    </div>
    {% endfor %}
</body>
</html>
"""


def update_vacancies():
    """Обновление списка вакансий"""
    print("Обновление вакансий...")
    new_vacancies = parse_vacancies()
    add_vacancies(new_vacancies)
    print(f"Добавлено: {len(new_vacancies)} вакансий")


# Настройка планировщика
scheduler = BackgroundScheduler()
scheduler.add_job(update_vacancies, 'interval', minutes=60)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


@app.route('/api/vacancies', methods=['GET'])
def api_vacancies():
    """API endpoint для получения вакансий в формате JSON"""
    vacancies = get_vacancies()
    return jsonify({'vacancies': vacancies})


@app.route('/', methods=['GET'])
@app.route('/vacancies', methods=['GET'])
def show_vacancies():
    """Endpoint для отображения вакансий в браузере"""
    vacancies = get_vacancies()
    return render_template_string(HTML_TEMPLATE, vacancies=vacancies)


if __name__ == '__main__':
    update_vacancies()  # Первоначальное обновление
    app.run(debug=True)
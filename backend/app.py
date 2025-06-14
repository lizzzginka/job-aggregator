import sqlite3
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash, make_response
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from hh_parser import parse_vacancies
from db import (
    init_db, add_vacancies, get_vacancies, get_vacancy_by_id,
    add_user, get_user, update_user_login, init_db, get_all_users,
    add_favorite, remove_favorite, get_favorites, is_favorite,
    set_employment, remove_employment, get_employment, get_all_employments,
    get_all_students_with_last_login, get_archived_students, archive_student, is_archived
)
from datetime import datetime, timedelta

from io import BytesIO
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import pytz
from io import StringIO
app = Flask(__name__)
app.secret_key = '987654321'
app.permanent_session_lifetime = timedelta(hours=1)
CORS(app)

init_db()


def update_vacancies():
    print("Обновление вакансий...")
    new_vacancies = parse_vacancies()
    add_vacancies(new_vacancies)
    print(f"Добавлено: {len(new_vacancies)} вакансий")


scheduler = BackgroundScheduler()
scheduler.add_job(update_vacancies, 'interval', minutes=60)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


@app.before_request
def before_request():
    session.permanent = True
    session.modified = True


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        group_number = request.form.get('group_number', None)

        user = get_user(full_name, password, user_type)

        # Для студентов проверяем совпадение группы
        if user and user['user_type'] == 'student' and group_number != user['group_number']:
            flash('Неверный номер группы', 'danger')
            return redirect(url_for('login'))

        if user:
            session['user_id'] = user['id']
            # Обновляем время последнего входа
            update_user_login(user['id'])
            return redirect(url_for('index'))
        else:
            flash('Неверные данные для входа', 'danger')

    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/confirm_employment/<int:vacancy_id>', methods=['POST'])
def confirm_employment(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'student':
        return jsonify({'error': 'Доступ запрещен'}), 403

    # Проверяем, есть ли уже трудоустройство
    current_employment = get_employment(user['id'])
    if current_employment:
        return jsonify({'error': 'Вы уже отметили трудоустройство'}), 400

    # Добавляем в избранное, если еще не добавлено
    if not is_favorite(user['id'], vacancy_id):
        add_favorite(user['id'], vacancy_id)

    # Отмечаем трудоустройство
    set_employment(user['id'], vacancy_id)

    return jsonify({'status': 'success'})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        group_number = request.form.get('group_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type')
        registration_code = request.form.get('registration_code', '')

        errors = []
        # Проверка ФИО на наличие цифр
        if any(char.isdigit() for char in full_name):
            errors.append('ФИО не должно содержать цифры')



        # Валидация данных
        if not full_name:
            errors.append('ФИО обязательно для заполнения')

        if user_type == 'student':
            if not group_number or not group_number.isdigit() or len(group_number) != 3:
                errors.append('Номер группы должен быть трехзначным числом')
        elif user_type == 'university':
            if registration_code != '987654321':
                errors.append('Неверный код регистрации')

        if not password or len(password) < 6:
            errors.append('Пароль должен содержать не менее 6 символов')
        elif password != confirm_password:
            errors.append('Пароли не совпадают')

        if not errors:
            # Хешируем пароль перед сохранением
            hashed_password = generate_password_hash(password)

            if user_type == 'university':
                group_number = None

            user_id = add_user(full_name, group_number, hashed_password, user_type)
            if user_id:
                flash('Регистрация прошла успешно. Теперь вы можете войти.', 'success')
                return redirect(url_for('login'))
            else:
                errors.append('Пользователь с такими данными уже существует')

        for error in errors:
            flash(error, 'danger')

    return render_template('register.html')


@app.route('/')
def index():
    search_query = request.args.get('search', '').lower()
    all_vacancies = get_vacancies()  # Теперь get_vacancies() уже возвращает отфильтрованные данные

    # Фильтрация по поисковому запросу
    if search_query:
        vacancies = [
            v for v in all_vacancies
            if (search_query in v['title'].lower() or
                search_query in v['company'].lower() or
                (v.get('description') and search_query in v['description'].lower()))
        ]
    else:
        vacancies = all_vacancies

    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])

    employment = None
    favorites = []
    if user:
        employment = get_employment(user['id'])
        favorites = [v['id'] for v in get_favorites(user['id'])]

    return render_template('index.html',
                         vacancies=vacancies,
                         user=user,
                         employment=employment,
                         favorites=favorites,
                         search_query=search_query)
@app.route('/favorites')
def favorites():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])  # Получаем данные пользователя
    if not user:
        return redirect(url_for('login'))

    fav_vacancies = get_favorites(user['id'])
    employment = get_employment(user['id'])

    # Если есть трудоустройство, перемещаем эту вакансию в начало
    if employment:
        # Удаляем вакансию с трудоустройством из общего списка (если она там есть)
        fav_vacancies = [v for v in fav_vacancies if v['id'] != employment['id']]
        # Добавляем в начало
        fav_vacancies.insert(0, employment)

    return render_template('favorites.html',
                           favorites=fav_vacancies,
                           employment=employment,
                           user=user)  # Добавляем user в контекст

@app.route('/toggle_favorite/<int:vacancy_id>', methods=['POST'])
def toggle_favorite(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user_id = session['user_id']
    if is_favorite(user_id, vacancy_id):
        remove_favorite(user_id, vacancy_id)
        return jsonify({'status': 'removed'})
    else:
        add_favorite(user_id, vacancy_id)
        return jsonify({'status': 'added'})


@app.route('/remove_employment', methods=['POST'])
def remove_employment_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'student':
        return jsonify({'error': 'Доступ запрещен'}), 403

    remove_employment(user['id'])
    return jsonify({'status': 'removed'})

@app.route('/set_employment/<int:vacancy_id>', methods=['POST'])
def set_employment_route(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'student':
        return jsonify({'error': 'Доступ запрещен'}), 403

    current_employment = get_employment(user['id'])
    if current_employment:
        return jsonify({
            'error': 'Вы уже отметили вакансию на трудоустройство',
            'marked_vacancy_id': current_employment['vacancy_id']
        }), 400

    # Добавляем в избранное, если еще не добавлена
    if not is_favorite(user['id'], vacancy_id):
        add_favorite(user['id'], vacancy_id)

    set_employment(user['id'], vacancy_id)
    return jsonify({'status': 'added'})

@app.route('/toggle_employment/<int:vacancy_id>', methods=['POST'])
def toggle_employment(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'student':
        return jsonify({'error': 'Доступ запрещен'}), 403

    vacancy = get_vacancy_by_id(vacancy_id)
    if not vacancy:
        return jsonify({'error': 'Вакансия не найдена'}), 404

    current_employment = get_employment(user['id'])

    if current_employment and current_employment['id'] == vacancy_id:
        remove_employment(user['id'])
        return jsonify({'status': 'removed'})
    elif current_employment:
        return jsonify({'error': 'Вы уже отметили трудоустройство'}), 400
    else:
        # Добавляем в избранное, если еще не добавлена
        if not is_favorite(user['id'], vacancy_id):
            add_favorite(user['id'], vacancy_id)

        set_employment(user['id'], vacancy_id)
        return jsonify({'status': 'added'})


# Добавим временную зону
chelyabinsk_tz = pytz.timezone('Asia/Yekaterinburg')  # Челбинское время (UTC+5)


@app.route('/remove_favorite/<int:vacancy_id>', methods=['POST'])
def remove_favorite_route(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user_id = session['user_id']

    # Проверяем, существует ли вакансия в избранном
    if not is_favorite(user_id, vacancy_id):
        return jsonify({'error': 'Вакансия не найдена в избранном'}), 404

    remove_favorite(user_id, vacancy_id)
    return jsonify({'status': 'removed'})

@app.route('/user_activity')
def user_activity():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user = get_user_by_id(session['user_id'])
        if not user or user['user_type'] != 'university':
            return redirect(url_for('index'))

        students = [s for s in get_all_students_with_last_login() if not is_archived(s['id'])]

        for student in students:
            if student['last_login']:
                try:
                    dt_str = student['last_login'].replace('T', ' ').split('.')[0]
                    dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    student['last_login'] = dt.strftime('%d.%m.%Y %H:%M')
                except ValueError as e:
                    student['last_login'] = 'Неверный формат времени'
                    print(f"Ошибка форматирования времени: {e}")
            else:
                student['last_login'] = 'Никогда'

        return render_template('user_activity.html',
                            students=students,
                            user=user)
    except Exception as e:
        print(f"Ошибка в user_activity: {str(e)}")
        flash('Произошла ошибка при загрузке страницы активности', 'danger')
        return redirect(url_for('index'))
@app.route('/employment_report')
def employment_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return redirect(url_for('index'))

    employments = get_all_employments()
    return render_template('employment_report.html', employments=employments, user=user)

def get_all_employments():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.full_name, u.group_number, v.company, v.url
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
        'company': e[2],
        'url': e[3]
    } for e in employments]


@app.route('/download_employment_report')
def download_employment_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return redirect(url_for('index'))

    employments = get_all_employments()

    # Создаем CSV с правильной кодировкой и BOM (для Excel)
    output = StringIO()
    output.write('\ufeff')  # Добавляем BOM для корректного отображения в Excel
    output.write("Группа,ФИО студента,Компания,Ссылка на вакансию\n")

    for emp in employments:
        line = f"{emp['group_number']},{emp['full_name']},{emp['company']},{emp['url']}\n"
        output.write(line)

    response = make_response(output.getvalue())

    # Устанавливаем правильные заголовки
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = 'attachment; filename=employment_report.csv'

    return response


def get_user_by_id(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, full_name, group_number, user_type FROM users WHERE id = ?
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


def archive_student(user_id):
    """Добавляет студента в архив"""
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        # Проверяем, не архивирован ли уже студент
        cursor.execute('SELECT 1 FROM archived_students WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            return False  # Уже в архиве

        cursor.execute('INSERT INTO archived_students (user_id) VALUES (?)', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Ошибка при архивации студента {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


@app.route('/archive_students', methods=['POST'])
def archive_students():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return jsonify({'error': 'Forbidden'}), 403

    try:
        # Получаем только активных студентов (не в архиве)
        active_students = [s for s in get_all_students_with_last_login()
                           if not is_archived(s['id'])]

        if not active_students:
            return jsonify({'error': 'Нет активных студентов для архивации'}), 400

        success_count = 0
        failed_ids = []

        for student in active_students:
            if not archive_student(student['id']):
                failed_ids.append(student['id'])
            else:
                success_count += 1

        if success_count == 0:
            return jsonify({
                'error': 'Не удалось архивировать ни одного студента',
                'failed_ids': failed_ids
            }), 400

        # Возвращаем обновленные списки
        return jsonify({
            'status': 'success',
            'archived_count': success_count,
            'failed_count': len(failed_ids),
            'active_students': len([s for s in get_all_students_with_last_login()
                                    if not is_archived(s['id'])]),
            'archived_students': len(get_archived_students())
        })
    except Exception as e:
        print(f"Ошибка в archive_students: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def is_archived(user_id):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    try:
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='archived_students'")
        if not cursor.fetchone():
            return False

        cursor.execute('SELECT 1 FROM archived_students WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Ошибка при проверке архивации: {e}")
        return False
    finally:
        conn.close()


@app.route('/get_active_students')
def get_active_students():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return jsonify({'error': 'Forbidden'}), 403

    try:
        students = [s for s in get_all_students_with_last_login()
                    if not is_archived(s['id'])]

        # Форматируем дату
        for student in students:
            if student['last_login']:
                try:
                    dt_str = student['last_login'].replace('T', ' ').split('.')[0]
                    dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    student['last_login'] = dt.strftime('%d.%m.%Y %H:%M')
                except ValueError:
                    student['last_login'] = 'Неверный формат'

        return jsonify(students)
    except Exception as e:
        print(f"Ошибка в get_active_students: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/get_archived_students')
def get_archived_students_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return jsonify({'error': 'Forbidden'}), 403

    try:
        archived = get_archived_students()
        # Форматируем дату последнего входа
        for student in archived:
            if student['last_login']:
                try:
                    dt_str = student['last_login'].replace('T', ' ').split('.')[0]
                    dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    student['last_login'] = dt.strftime('%d.%m.%Y %H:%M')
                except ValueError:
                    student['last_login'] = 'Неверный формат'
        return jsonify(archived)
    except Exception as e:
        print(f"Ошибка в get_archived_students: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    update_vacancies()
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)

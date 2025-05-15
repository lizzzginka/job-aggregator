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
    set_employment, remove_employment, get_employment, get_all_employments
)
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from werkzeug.security import generate_password_hash

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

        user = get_user(full_name, password, user_type)
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            flash('Неверные данные для входа', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


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
    vacancies = get_vacancies()
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
                           favorites=favorites)


@app.route('/favorites')
def favorites():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    employment = get_employment(user['id'])
    fav_vacancies = get_favorites(user['id'])

    # Если есть трудоустройство, перемещаем его в начало списка
    if employment:
        employment_vacancy = next((v for v in fav_vacancies if v['id'] == employment['id']), None)
        if employment_vacancy:
            fav_vacancies.remove(employment_vacancy)
            fav_vacancies.insert(0, employment_vacancy)

    return render_template('favorites.html',
                           favorites=fav_vacancies,
                           user=user,
                           employment=employment)


@app.route('/toggle_favorite/<int:vacancy_id>', methods=['POST'])
def toggle_favorite(vacancy_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    vacancy = get_vacancy_by_id(vacancy_id)
    if not vacancy:
        return jsonify({'error': 'Вакансия не найдена'}), 404

    if is_favorite(user['id'], vacancy_id):
        remove_favorite(user['id'], vacancy_id)
        return jsonify({'status': 'removed'})
    else:
        if add_favorite(user['id'], vacancy_id):
            return jsonify({'status': 'added'})
        else:
            return jsonify({'error': 'Не удалось добавить в избранное'}), 500


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
        if set_employment(user['id'], vacancy_id):
            return jsonify({'status': 'added'})
        else:
            return jsonify({'error': 'Не удалось отметить трудоустройство'}), 500

@app.route('/user_activity')
def user_activity():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return redirect(url_for('index'))

    users = get_all_users()
    return render_template('user_activity.html', users=users, user=user)


@app.route('/employment_report')
def employment_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return redirect(url_for('index'))

    employments = get_all_employments()
    return render_template('employment_report.html', employments=employments, user=user)


@app.route('/download_employment_report')
def download_employment_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user or user['user_type'] != 'university':
        return redirect(url_for('index'))

    employments = get_all_employments()

    df = pd.DataFrame(employments)
    df.columns = ['ФИО студента', 'Группа', 'Вакансия', 'Компания', 'Ссылка']

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Трудоустройства', index=False)
    writer.close()
    output.seek(0)

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = 'attachment; filename=employment_report.xlsx'

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


if __name__ == '__main__':
    update_vacancies()
    app.run(debug=True)
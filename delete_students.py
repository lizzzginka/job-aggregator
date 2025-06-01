import sqlite3
import os

def delete_all_students():
    db_path = os.path.join('backend', 'vacancies.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Удаляем всех студентов
    cursor.execute("DELETE FROM users WHERE user_type = 'student'")

    # Очищаем связанные данные
    cursor.execute("DELETE FROM favorites")
    cursor.execute("DELETE FROM employment")

    conn.commit()
    conn.close()
    print("Все студенты и связанные данные успешно удалены!")


if __name__ == '__main__':
    delete_all_students()
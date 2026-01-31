import sqlite3
from config import DATABASE

# Набор предустановленных навыков и статусов для заполнения БД по-умолчанию.
# Формат — список кортежей, пригодный для executemany
skills = [ (_,) for _ in (['Python', 'SQL', 'API', 'Telegram'])]
statuses = [ (_,) for _ in (['На этапе проектирования', 'В процессе разработки', 'Разработан. Готов к использованию.', 'Обновлен', 'Завершен. Не поддерживается'])]

class DB_Manager:
    """Менеджер работы с SQLite базой данных проектов.

    Экземпляр управляет соединениями и предоставляет методы для
    создания таблиц, вставки и выборки данных, а также обновления и удаления.
    """
    def __init__(self, database):
        # Путь к файлу базы данных
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            # Таблица проектов
            conn.execute('''CREATE TABLE projects (
                            project_id INTEGER PRIMARY KEY,
                            user_id INTEGER,
                            project_name TEXT NOT NULL,
                            description TEXT,
                            url TEXT,
                            status_id INTEGER,
                            FOREIGN KEY(status_id) REFERENCES status(status_id)
                        )''') 
            # Справочник навыков
            conn.execute('''CREATE TABLE skills (
                            skill_id INTEGER PRIMARY KEY,
                            skill_name TEXT
                        )''')
            # Связующая таблица many-to-many для проектов и навыков
            conn.execute('''CREATE TABLE project_skills (
                            project_id INTEGER,
                            skill_id INTEGER,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(skill_id) REFERENCES skills(skill_id)
                        )''')
            # Справочник статусов проекта
            conn.execute('''CREATE TABLE status (
                            status_id INTEGER PRIMARY KEY,
                            status_name TEXT
                        )''')
            conn.commit()
        print("База данных успешно создана.")

    def __executemany(self, sql, data):
        """Выполнить executemany для переданного SQL и списка данных.

        Используется для батч-операций INSERT/UPDATE/DELETE.
        """
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany(sql, data)
            conn.commit()

    def __select_data(self, sql, data = tuple()):
        """Выполнить SELECT-запрос и вернуть все результаты.

        Параметр `data` по умолчанию — пустой кортеж для запросов без параметров.
        """
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute(sql, data)
            return cur.fetchall()
            

    def default_insert(self):
        """Вставить предопределённые записи в таблицы skills и status.

        Используется после инициализации (create_tables), чтобы заполнить
        базу начальными значениями без дублирования (OR IGNORE).
        """
        sql = 'INSERT OR IGNORE INTO skills (skill_name) values(?)'
        data = skills
        self.__executemany(sql, data)
        sql = 'INSERT OR IGNORE INTO status (status_name) values(?)'
        data = statuses
        self.__executemany(sql, data)


    def insert_project(self, data):
        """Вставить один или несколько проектов.

        Параметр `data` ожидается в формате списка кортежей,
        подходящем для executemany: [(user_id, name, url, status_id), ...]
        """
        sql = 'INSERT OR IGNORE INTO projects (user_id, project_name, url, status_id) values(?, ?, ?, ?)'
        self.__executemany(sql, data)

    def insert_skill(self, user_id, project_name, skill):
        """Добавить навык к проекту.

        Находит id проекта и id навыка по именам, затем вставляет запись
        в `project_skills`.
        """
        sql = 'SELECT project_id FROM projects WHERE project_name = ? AND user_id = ?'
        project_id = self.__select_data(sql, (project_name, user_id))[0][0]
        skill_id = self.__select_data('SELECT skill_id FROM skills WHERE skill_name = ?', (skill,))[0][0]
        data = [(project_id,skill_id)]
        sql = 'INSERT OR IGNORE INTO project_skills VALUES (?, ?)'
        self.__executemany(sql, data)

  
    def get_statuses(self):
        """Вернуть список названий статусов."""
        sql='SELECT status_name from status'
        return self.__select_data(sql)
        
    def get_status_id(self, status_name):
        """Вернуть id статуса по его названию, либо None, если не найден."""
        sql = 'SELECT status_id FROM status WHERE status_name = ?'
        res = self.__select_data(sql, (status_name,))
        if res: return res[0][0]
        else: return None

    def get_projects(self, user_id):
        """Получить все проекты пользователя."""
        return self.__select_data(sql='SELECT * FROM projects WHERE user_id = ?', data = (user_id,))

    def get_project_id(self, project_name, user_id):
        """Вернуть project_id по имени проекта и id пользователя."""
        return self.__select_data(sql='SELECT project_id FROM projects WHERE project_name = ? AND user_id = ?  ', data = (project_name, user_id,))[0][0]

    def get_skills(self):
        """Вернуть все навыки из справочника skills."""
        return self.__select_data(sql='SELECT * FROM skills')
    
    def get_project_skills(self, project_name):
        """Вернуть строку со списком навыков, привязанных к проекту.

        Результат — строка, где навыки разделены запятой. Если навыков нет,
        вернётся пустая строка.
        """
        res = self.__select_data(sql='''SELECT skill_name FROM projects 
    JOIN project_skills ON projects.project_id = project_skills.project_id 
    JOIN skills ON skills.skill_id = project_skills.skill_id 
    WHERE project_name = ?''', data = (project_name,) )
        return ', '.join([x[0] for x in res])
    
    def get_project_info(self, user_id, project_name):
        sql = """
SELECT project_name, description, url, status_name FROM projects 
JOIN status ON
status.status_id = projects.status_id
WHERE project_name=? AND user_id=?
"""
        # Возвращает список строк (обычно одна строка) с информацией о проекте
        return self.__select_data(sql=sql, data = (project_name, user_id))
    

    def update_projects(self, param, data):
        """Обновить поле `param` у проекта.

        Параметр `data` — кортеж в формате (new_value, project_name, user_id).
        """
        self.__executemany(f"UPDATE projects SET {param} = ? WHERE project_name = ? AND user_id = ?", [data]) # data ('atr', 'mew', 'name', 'user_id')


    def delete_project(self, user_id, project_id):
        """Удалить проект по user_id и project_id."""
        sql = "DELETE FROM projects WHERE user_id = ? AND project_id = ? "
        self.__executemany(sql, [(user_id, project_id)])

    def delete_skill(self, project_id, skill_id):
        """Удалить связь/навык у проекта (если используется).

        Примечание: текущая реализация удаляет запись из `skills` по skill_id и project_id,
        тогда как структура таблицы `skills` не содержит project_id — это может быть ошибкой.
        """
        sql = "DELETE FROM skills WHERE skill_id = ? AND project_id = ? "
        self.__executemany(sql, [(skill_id, project_id)])


if __name__ == '__main__':
    manager = DB_Manager(DATABASE)
    manager.create_tables()
    manager.default_insert()

import sys
import sqlite3
from os.path import isfile
import uis_pack

from PyQt5.QtGui import QPixmap, QCloseEvent
from PyQt5.QtWidgets import QWidget, QTextEdit, QFrame, QHeaderView, QListWidgetItem
from PyQt5.QtWidgets import QTableWidgetItem, QApplication, QPushButton, \
    QDialog, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt


#  кнопка с возможностью передать ей доп. параметр при инициилизации
class PushButtonWithinfo(QPushButton):
    def __init__(self, parent=None, info=''):
        super(PushButtonWithinfo, self).__init__(parent)
        self.info = info


# класс запускателя игр
class PageView(QDialog):
    def __init__(self, parent=None, base_name=None):
        super(PageView, self).__init__(parent)
        self.BASE_NAME = base_name
        self.con = sqlite3.connect(self.BASE_NAME)
        cur = self.con.cursor()
        self.start_screen_id = int(cur.execute(f'''SELECT link FROM buttons 
            WHERE is_restart = 1''').fetchone()[0])
        self.screen_id = self.start_screen_id
        self.restart_text, self.restart_id = cur.execute(
            f'''SELECT text, id FROM buttons WHERE is_restart = 1''').fetchone()
        self.initUI()

    def initUI(self):
        cur = self.con.cursor()
        self.setFixedSize(400, 700)
        game_name = cur.execute('SELECT name FROM description').fetchone()[0]
        self.setWindowTitle(str(game_name))
        # создаем поле для текста со всеми стилями
        self.textEdit = QTextEdit(self)
        self.textEdit.setFontPointSize(11)
        self.textEdit.move(20, 20)
        self.textEdit.resize(360, 300)
        self.textEdit.setReadOnly(True)
        self.textEdit.setStyleSheet('background-color: rgb(240, 240, 240);')
        self.textEdit.setFrameShape(QFrame.NoFrame)

        self.textEdit.setText(str(cur.execute(f'''SELECT text FROM screens 
            WHERE id = {self.screen_id}''').fetchone()[0]))

        labels = cur.execute(f'''SELECT text, id FROM buttons WHERE id in 
            (SELECT button_id FROM buttons_to_screens WHERE screen_id = {self.screen_id})''').fetchall()
        if not labels:
            labels = [[self.restart_text, self.restart_id]]
        self.buttons = []
        for i in range(len(labels)):
            self.buttons.append(PushButtonWithinfo(self, info=labels[i][1]))
            self.buttons[i].setText(str(labels[i][0]))
            self.buttons[i].move(20, 630 - i * 65)
            self.buttons[i].resize(360, 60)
            self.buttons[i].clicked.connect(self.variant_choose)

        cur.close()

    def update_screen(self):
        # обноляем экран в зависимоти от id экрана на который смотрим
        cur = self.con.cursor()
        self.textEdit.setText(str(cur.execute(f'''SELECT text FROM screens 
            WHERE id = {self.screen_id}''').fetchone()[0]))
        for i in self.buttons:
            i.hide()
        labels = cur.execute(f'''SELECT text, id FROM buttons WHERE id in 
                    (SELECT button_id FROM buttons_to_screens 
                    WHERE screen_id = {self.screen_id})''').fetchall()
        if not labels:
            labels = [[self.restart_text, self.restart_id]]
        for i in range(len(labels)):
            try:
                self.buttons[i].show()
                self.buttons[i].setText(str(labels[i][0]))
                self.buttons[i].info = labels[i][1]
            except IndexError:
                self.buttons.append(PushButtonWithinfo(self, info=labels[i][1]))
                self.buttons[i].setText(str(labels[i][0]))
                self.buttons[i].move(20, 630 - i * 65)
                self.buttons[i].resize(360, 60)
                self.buttons[i].show()
        cur.close()

    def variant_choose(self):
        # с помощью кнопки с доп информацией находим id нового экрана
        cur = self.con.cursor()
        temp = cur.execute(f'''SELECT link FROM buttons WHERE id = {self.sender().info}''').fetchone()[0]
        if temp is None:
            return None
        else:
            self.screen_id = temp
            cur.close()
            self.update_screen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F1:
            # вызов справки
            text = 'Играйте! Нажмите на один из вариантов и перейдите' + \
                   ' на новый экран или очутитесь на первом.'
            hw = help_window(self, text=text)
            hw.exec_()


# класс для быстрого рисования таблиц на вход получает матрицу, и отоброжает её в tableWidget
class TablePainter:
    def __init__(self, table):
        self.table = table

    def draw_new(self, items):
        self.table.setRowCount(0)
        self.table.setRowCount(len(items))
        for i in range(len(items)):
            for j in range(len(items[i])):
                self.table.setItem(i, j, QTableWidgetItem(str(items[i][j])))


# окно справки на вход получает текст для отображения
class help_window(QDialog, uis_pack.help_ui):
    def __init__(self, parent=None, text=''):
        super(help_window, self).__init__(parent)
        self.setupUi(self)
        self.help.setText(str(text))


# окно создания новой игры
class game_creator(QDialog, uis_pack.game_create_ui):
    def __init__(self, parent=None):
        super(game_creator, self).__init__(parent)
        self.setupUi(self)
        self.button_send = False
        self.create_button.clicked.connect(self.create_game)

    def create_game(self):
        # создание игры
        base_name = self.base_name_line.text()
        game_name = self.game_name_line.text()
        start_screen_key = self.start_screen_key_btn.text()
        restart_button = self.restart_button_text.toPlainText()
        # проверка на наличие запрещенных в системе Windows знаков в именах файлов
        # (и ещё точка чтобы не дать пользователю задать своё расширение)
        r = r'*|:"<>?\/.'
        for i in r:
            if base_name.count(i) > 0:
                em = QMessageBox(self)
                em.setText('Создание не удалось!\nНазвание базы данных содержит' +
                           r' запрещённый символ, один из:*|\:"<>?/.')
                em.exec_()
                return None
        if isfile(base_name + '.db'):
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nБаза с таким именем уже лежит в папке приложения.')
            em.exec_()
            return None
        if not start_screen_key:
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nКлюч начального экрана не может быть пустым.')
            em.exec_()
            return None
        if not game_name:
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nНазвание игры не может быть пустым.')
            em.exec_()
            return None
        if not base_name:
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nНазвание базы данных не может быть пустым.')
            em.exec_()
            return None
        # создаем базу
        con = sqlite3.connect(base_name + '.db')
        cur = con.cursor()
        cur.execute('''CREATE TABLE screens (
            id    INTEGER PRIMARY KEY
                          NOT NULL,
            text  TEXT    NOT NULL,
            [key] TEXT    NOT NULL
                          UNIQUE
        );''')
        cur.execute('''CREATE TABLE buttons (
                id         INTEGER PRIMARY KEY
                                   UNIQUE
                                   NOT NULL,
                text       TEXT    NOT NULL,
                link       INTEGER REFERENCES screens (id),
                is_restart BOOLEAN NOT NULL
            );''')
        cur.execute('''CREATE TABLE buttons_to_screens (
            button_id INTEGER REFERENCES buttons (id) 
                              NOT NULL,
            screen_id INTEGER REFERENCES screens (id) 
                              NOT NULL
        );''')
        cur.execute('''CREATE TABLE description (
            name STRING NOT NULL
        );''')
        # заполняем важными для начала работы данными, а именно кнопку рестарта, начальный экран, название игры
        # (начальный экрна неприкосновенен, потому что на него обязательно должна ссылаться кнопка рестарта)
        cur.execute(f'''INSERT INTO screens(text, key) VALUES("", "{start_screen_key}")''')
        cur.execute(f'''INSERT INTO description(name) VALUES("{game_name}")''')
        cur.execute(f'''INSERT INTO buttons(text, link, is_restart) VALUES("{restart_button}", 
            {cur.execute("SELECT id FROM screens").fetchone()[0]}, 1)''')
        con.commit()
        em = QMessageBox(self)
        em.setText('Создание прошло удачно!')
        em.exec_()
        cur.close()
        con.close()
        self.button_send = True
        self.close()

    def keyPressEvent(self, event):
        if int(event.modifiers()) == Qt.ControlModifier:
            # дублирование функций кнопки сочетанием клавиш
            if event.key() == Qt.Key_S:
                self.create_game()
        else:
            if event.key() == Qt.Key_F1:
                text = 'Создание новой игры\n\n1) Укажите название базы данных без расширения\n' + \
                       '2) Укажите не пустое название игры\n3) Укажите не пустой ключ начального экрана\n' + \
                       '4) И укажите текст на кнопке рестарта(его можно изменить потом)'
                hw = help_window(self, text=text)
                hw.exec_()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.button_send:
            reply = QMessageBox.question(self, 'Закрытие окна', "Вы не создали игру.\n"
                                                                "Вы уверены, что хотите уйти?",
                                         QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()


# окно создания нового экрана
class new_screen_configurator(QDialog, uis_pack.new_screen_configurator_ui):
    def __init__(self, parent=None, base_name=None):
        self.BASE_NAME = base_name
        self.button_send = False
        super(new_screen_configurator, self).__init__(parent)
        self.setupUi(self)
        self.con = sqlite3.connect(self.BASE_NAME)
        self.create_btn.clicked.connect(self.create_screen)

    def create_screen(self):
        text = self.text_line.toPlainText()
        key = self.key_line.text()
        cur = self.con.cursor()
        # ищем экраны с такими же ключами, потому что ключ уникален
        equal = cur.execute(f'''SELECT text FROM screens WHERE key = "{key}"''').fetchall()
        if key == '':
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nНельзя задавать пустой ключ!')
            em.exec_()
            cur.close()
            return None
        if not equal:
            cur.execute(f'''INSERT INTO screens(text, key) VALUES("{text}", "{key}")''')
            screen_id = int(cur.execute(f'''SELECT id FROM screens WHERE key = "{key}"''').fetchone()[0])
            self.con.commit()
            self.parent().config_new_screen(True, screen_id)
            self.button_send = True
            self.close()
        else:
            em = QMessageBox(self)
            em.setText('Создание не удалось!\nТакой ключ уже существует')
            em.exec_()
        cur.close()

    def keyPressEvent(self, event):
        if int(event.modifiers()) == Qt.ControlModifier:
            # дублирование функии кнопки
            if event.key() == Qt.Key_S:
                self.create_screen()
        else:
            if event.key() == Qt.Key_F1:
                text = 'Создайте экран в этом окне, вам не обязательно писать сейчас текст для него,' + \
                       ' достаточно указать ключ.\n\nСочетание клавиш Ctrl+S создаст экран.'
                hw = help_window(self, text=text)
                hw.exec_()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.button_send:
            reply = QMessageBox.question(self, 'Закрытие окна', "Вы не создали экран.\n"
                                                                "Вы уверены, что хотите уйти?",
                                         QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()


class button_configurator(QDialog, uis_pack.button_configurator_ui):
    def __init__(self, parent=None, base_name=None):
        self.BASE_NAME = base_name
        super(button_configurator, self).__init__(parent)
        self.is_edit = False
        self.button_close = False
        self.setupUi(self)
        self.saveButton.clicked.connect(self.save_button)
        self.con = sqlite3.connect(self.BASE_NAME)
        cur = self.con.cursor()
        self.linkBox.addItems([''] + [i[0] for i in cur.execute(f'''SELECT key FROM screens''').fetchall()])
        cur.close()

    # конфигурация формы на случай,если она не создает новую кнопку, а редактирует старую
    def config(self, screen_id, bi=1, bl=1, is_edit=False):
        self.screen_id = screen_id
        self.is_edit = is_edit
        if self.is_edit:
            self.difficult_id = bi
            self.link = bl
            cur = self.con.cursor()
            link_text = cur.execute(f'''SELECT key FROM screens WHERE id = 
                {self.link}''').fetchone()[0] if not (self.link is None) else ''
            difficult_text = cur.execute(f'''SELECT text FROM buttons 
                WHERE id = {self.difficult_id}''').fetchone()[0]
            cur.close()
            self.buttonText.setPlainText(str(difficult_text))
            self.linkBox.setCurrentIndex(self.linkBox.findText(link_text))

    def save_button(self):
        cur = self.con.cursor()
        text = self.buttonText.toPlainText()
        link = self.linkBox.currentText()
        if self.is_edit:
            # если это было редактирование кнопки
            if link:
                cur.execute(f'''UPDATE buttons SET text = "{text}", link = 
                    {cur.execute(f'SELECT id FROM screens WHERE key = "{link}"').fetchone()[0]}, 
                    is_restart = 0 WHERE id = {self.difficult_id}''')
            else:
                cur.execute(f'''UPDATE buttons SET text = "{text}", is_restart = 0 
                    WHERE id = {self.difficult_id}''')
            cur.execute(f'''UPDATE buttons_to_screens SET screen_id = {self.screen_id} 
                WHERE button_id = {self.difficult_id}''')
        else:
            # если создаем новую
            new_screen_id = max([i[0] for i in cur.execute('SELECT id FROM buttons').fetchall()]) + 1
            if link:
                new_link = cur.execute(f"""SELECT id FROM screens WHERE key = '{link}'""").fetchone()[0]
                cur.execute(f'''INSERT INTO buttons(id, text, link, is_restart) 
                    VALUES({new_screen_id}, "{text}", {new_link}, 0)''')
            else:
                cur.execute(f'''INSERT INTO buttons(id, text, is_restart) 
                            VALUES({new_screen_id}, "{text}", 0)''')
            cur.execute(f'''INSERT INTO buttons_to_screens(button_id, screen_id) 
                VALUES({new_screen_id}, {self.screen_id})''')
        self.con.commit()
        cur.close()
        self.button_close = True
        self.close()

    def keyPressEvent(self, event):
        if int(event.modifiers()) == Qt.ControlModifier:
            # дублирование функций кнопки сочетанием клавиш
            if event.key() == Qt.Key_S:
                self.save_button()
        else:
            if event.key() == Qt.Key_F1:
                text = 'Создайте текстовую кнопку для вашего экрана, и укажите на какой' + \
                       ' экран она переведет игрока.\n\nСочетание клавиш Ctrl+S создаст кнопку.'
                hw = help_window(self, text=text)
                hw.exec_()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.button_close:
            reply = QMessageBox.question(self, 'Закрытие окна', 'Вы не сохранили кнопку.\n'
                                                                'Вы уверены, что хотите уйти?',
                                         QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()


# окно редактирования экрана
class screen_configurator(QDialog, uis_pack.screen_configurator_ui):
    def __init__(self, parent=None, screen_id=1, base_name=None):
        self.BASE_NAME = base_name
        super(screen_configurator, self).__init__(parent)
        self.setupUi(self)
        self.is_edited = False
        self.screen_id = screen_id
        self.add_button.clicked.connect(self.create_button)
        self.change_button.clicked.connect(self.change_selected_button)
        self.delete_button.clicked.connect(self.del_button)
        self.save_button.clicked.connect(self.save_screen)
        self.screen_text_palne.textChanged.connect(self.load_preview)
        self.con = sqlite3.connect(self.BASE_NAME)
        cur = self.con.cursor()
        # первоначальная загрузка превью игры отличается от последующего обновления
        # и поэтому не вынесена в функцию
        labels = [i[0] for i in cur.execute(f'''SELECT text FROM buttons WHERE id in 
                    (SELECT button_id FROM buttons_to_screens 
                    WHERE screen_id = {self.screen_id})''').fetchall()]
        self.buttons = []
        for i in range(len(labels)):
            self.buttons.append(QPushButton(self))
            self.buttons[i].setText(str(labels[i]))
            self.buttons[i].move(40, 630 - i * 65)
            self.buttons[i].resize(360, 60)
        cur.close()
        self.load_text_ind()
        self.load_buttons()
        self.screen_text_palne.textChanged.connect(self.make_edited)
        self.id_line.textChanged.connect(self.make_edited)

    def load_buttons(self):
        # обновление кнопок в списке
        self.button_list.clear()
        cur = self.con.cursor()
        data = cur.execute(f'''SELECT text, id FROM buttons WHERE id in 
            (SELECT button_id FROM buttons_to_screens 
            WHERE screen_id = {self.screen_id})''').fetchall()
        cur.close()
        for q in data:
            temp = QListWidgetItem(q[0])
            temp.setData(Qt.UserRole, q[1])
            self.button_list.addItem(temp)
        self.load_preview()

    def load_preview(self):
        # обновление превью игры
        self.screen_text.setText(self.screen_text_palne.toPlainText())
        for i in self.buttons:
            i.hide()
        cur = self.con.cursor()
        labels = [i[0] for i in cur.execute(f'''SELECT text FROM buttons WHERE id in 
                    (SELECT button_id FROM buttons_to_screens 
                    WHERE screen_id = {self.screen_id})''').fetchall()]
        if not labels:
            labels = [cur.execute('SELECT text FROM buttons WHERE is_restart = 1').fetchone()[0]]
        for i in range(len(labels)):
            try:
                self.buttons[i].show()
                self.buttons[i].setText(str(labels[i]))
            except IndexError:
                self.buttons.append(QPushButton(self))
                self.buttons[i].setText(str(labels[i]))
                self.buttons[i].move(40, 630 - i * 65)
                self.buttons[i].resize(360, 60)
                self.buttons[i].show()
        cur.close()

    def create_button(self):
        # открываем окно создания кнопки
        # ограничитель в 5 кнопок на один экран, чтобы они не заезжали на текст
        cur = self.con.cursor()
        num = len(cur.execute(f'''SELECT id FROM buttons WHERE id in 
                    (SELECT button_id FROM buttons_to_screens WHERE screen_id = {self.screen_id})''').fetchall())
        cur.close()
        if num == 5:
            em = QMessageBox(self)
            em.setText('Добавление не удалось!\nНа экране возможно максимум 5 кнопок!')
            em.exec_()
            return None
        dialog = button_configurator(self, base_name=self.BASE_NAME)
        dialog.config(self.screen_id)
        dialog.exec_()
        self.load_buttons()

    def del_button(self):
        # удаление выделенной кнопки
        if not self.button_list.selectedItems():
            return None
        button_id = self.button_list.selectedItems()[0].data(Qt.UserRole)
        print(button_id)
        cur = self.con.cursor()
        cur.execute(f'''DELETE FROM buttons WHERE id = {button_id}''')
        cur.execute(f'''DELETE FROM buttons_to_screens WHERE button_id = {button_id}''')
        self.con.commit()
        cur.close()
        self.load_buttons()

    def change_selected_button(self):
        # изменяет выделенную кнопку
        if not self.button_list.selectedItems():
            return None
        button_id = self.button_list.selectedItems()[0].data(Qt.UserRole)
        cur = self.con.cursor()
        button_link = cur.execute(f'''SELECT link FROM buttons 
            WHERE id = {self.button_list.selectedItems()[0].data(Qt.UserRole)}''').fetchone()[0]
        cur.close()
        dialog = button_configurator(self, base_name=self.BASE_NAME)
        dialog.config(self.screen_id, bi=button_id, bl=button_link, is_edit=True)
        dialog.exec_()
        self.load_buttons()

    def save_screen(self):
        # сохранение информации об окне
        text = self.screen_text_palne.toPlainText()
        key = self.id_line.text()
        if not key:
            em = QMessageBox(self)
            em.setText('Сохранение не удалось!\nКлюч не может быть пустым')
            em.exec_()
            return None
        cur = self.con.cursor()
        equal = cur.execute(f'''SELECT text FROM screens 
            WHERE key = "{key}" AND NOT id = {self.screen_id}''').fetchall()
        if not equal:
            cur.execute(f'''UPDATE screens SET text = "{text}", key = "{key}" 
            WHERE id = {self.screen_id}''')
            self.con.commit()
            self.is_edited = False
            em = QMessageBox(self)
            em.setText('Сохранение прошло удачно!')
            em.exec_()
        else:
            em = QMessageBox(self)
            em.setText('Сохранение не удалось!\nТакой ключ уже существует')
            em.exec_()
        cur.close()

    def load_text_ind(self):
        # заполнение формы данными из базы данных
        cur = self.con.cursor()
        text, key = cur.execute(f'''SELECT text, key FROM screens
            WHERE id = {self.screen_id}''').fetchone()
        self.screen_text_palne.setPlainText(text)
        self.id_line.setText(str(key))

    def keyPressEvent(self, event):
        if int(event.modifiers()) == Qt.ControlModifier:
            if event.key() == Qt.Key_S:
                # дублирование функции кнопки сочетанием клавиш
                self.save_screen()
        else:
            if event.key() == Qt.Key_F1:
                text = '-Вы можете создать, редактировать или удалить кнопку.\n' + \
                       '-Также вы можете изменить текст на экране или его ключ\n' + \
                       '-Слева от области редактирования видно превью того что будет видет игрок\n\n' + \
                       '-Сочетание клавиш Ctrl+S сохранит текст и ключ экрана.\n\n\n' + \
                       'P.S.Сохранение названия и текста независимо от редактирования кнопок'
                hw = help_window(self, text=text)
                hw.exec_()

    def make_edited(self):
        self.is_edited = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_edited:
            reply = QMessageBox.question(self, 'Закрытие окна', 'Вы не сохранили изменения в тексте' +
                                         ' экрана и ключе.\n' +
                                         'Вы уверены, что хотите уйти?',
                                         QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()


# основной экран редактирования игры
class main_edit_page(QDialog, uis_pack.main_edit_page_ui):
    def __init__(self, parent=None, base_name=None):
        super(main_edit_page, self).__init__(parent)
        self.BASE_NAME = base_name
        self.setupUi(self)
        self.con = sqlite3.connect(self.BASE_NAME)
        self.new_screen_created = False
        self.new_screen_index = None
        self.is_edited = False
        self.open_selected_screen_btn.clicked.connect(self.open_screen)
        self.delete_screen_btn.clicked.connect(self.delete_screen)
        self.new_screen_btn.clicked.connect(self.create_screen)
        self.search_btn.clicked.connect(self.load_screens)
        self.save_button.clicked.connect(self.change_game_name)
        self.table_painter = TablePainter(self.screen_table)
        self.screen_table.doubleClicked.connect(self.open_screen)
        hh = self.screen_table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.load_screens()
        self.load_game_name()
        self.load_restart_name()
        self.restart_name_btn.textEdited.connect(self.make_edited)
        self.name_text_edit.textEdited.connect(self.make_edited)

    def load_screens(self):
        # загрузка списка экранов с фильтров
        cur = self.con.cursor()
        if self.filter_box.currentText() == 'По ключу':
            filt = 'key'
        else:
            filt = 'text'
        search = self.filter_line.text()
        data = [[i[0], i[1]] for i in cur.execute(f'''SELECT key, text FROM screens 
            WHERE {filt} like "%{search}%"''').fetchall()]
        self.table_painter.draw_new(data)

    def get_selected_item(self):
        # Получение выделеного экрана
        if not self.screen_table.selectedItems():
            return None
        screen_ind = self.screen_table.selectedItems()[0].text()
        cur = self.con.cursor()
        screen_id = int(cur.execute(f'''SELECT id FROM screens WHERE key = "{screen_ind}"''').fetchone()[0])
        cur.close()
        return screen_id

    def create_screen(self):
        # создание нового экрана
        cs = new_screen_configurator(self, base_name=self.BASE_NAME)
        cs.exec_()
        self.load_screens()
        if self.new_screen_created:
            screen_id = self.new_screen_index
            sc = screen_configurator(self, screen_id=screen_id, base_name=self.BASE_NAME)
            sc.exec_()
            self.new_screen_created = False
        self.load_screens()

    def open_screen(self):
        # открыть экран
        screen_id = self.get_selected_item()
        if screen_id is None:
            return None
        sc = screen_configurator(self, screen_id=screen_id, base_name=self.BASE_NAME)
        sc.exec_()
        self.load_screens()

    def delete_screen(self):
        # удаление экрана со всеми связями которые к нему закреплены
        screen_id = self.get_selected_item()
        if screen_id is None:
            return None
        cur = self.con.cursor()
        start_id = int(cur.execute(f'''SELECT link FROM buttons WHERE is_restart = 1''').fetchone()[0])
        if screen_id == start_id:
            em = QMessageBox(self)
            em.setText('Удаление не удалось!\nСтартовый экран нельзя удалить')
            em.exec_()
            return None
        # связь экрана с кнопками
        cur.execute(f'''DELETE FROM buttons_to_screens WHERE screen_id = {screen_id}''')
        # очистка ссылки у кнопок
        cur.execute(f'''UPDATE buttons SET link = NULL WHERE link = {screen_id}''')
        # удаление самой записи экрана
        cur.execute(f'''DELETE FROM screens WHERE id = {screen_id}''')
        self.con.commit()
        cur.close()
        self.load_screens()

    def config_new_screen(self, is_created, screen_index):
        # важные флаги для контроля создания нового экрана
        self.new_screen_created = is_created
        self.new_screen_index = screen_index

    def load_game_name(self):
        # получить название игры
        cur = self.con.cursor()
        name = cur.execute('''SELECT name FROM description''').fetchone()[0]
        self.name_text_edit.setText(str(name))

    def load_restart_name(self):
        # получение названия кнопки рестарта в базе
        cur = self.con.cursor()
        restart_name = cur.execute('''SELECT text FROM buttons WHERE is_restart = 1''').fetchone()[0]
        self.restart_name_btn.setText(str(restart_name))

    def change_game_name(self):
        # изменение названия игры и текста на кнопке рестарта в базе
        name = self.name_text_edit.text()
        restart_name = self.restart_name_btn.text()
        cur = self.con.cursor()
        cur.execute(f'UPDATE description SET name = "{name}"')
        cur.execute(f'UPDATE buttons SET text = "{restart_name}" WHERE is_restart=1')
        self.con.commit()
        self.is_edited = False
        em = QMessageBox(self)
        em.setText('Сохранение прошло удачно!')
        em.exec_()
        cur.close()

    def make_edited(self):
        self.is_edited = True

    def keyPressEvent(self, event):
        if int(event.modifiers()) == Qt.ControlModifier:
            if event.key() == Qt.Key_S:
                # дублирование функционала кнопки сочетанием клавиш
                self.change_game_name()
        else:
            if event.key() == Qt.Key_F1:
                text = '-Создайте новый экран, если расказать игроку новый случай в жизни его героя.\n' + \
                       '-Редактируйте экран, если случай, созданный вами, чем-то вам не понравился.\n' + \
                       '-Удалите экран, если он вам совсем не понравился.\n\n' + \
                       'Сочетание клавиш Ctrl+S сохранит название игры и текст на кнопке рестарта.'
                hw = help_window(self, text=text)
                hw.exec_()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_edited:
            reply = QMessageBox.question(self, 'Закрытие окна', 'Вы не сохранили изменения в названии' +
                                         ' игры и кнопке рестарта.\n' +
                                         'Вы уверены, что хотите уйти?',
                                         QMessageBox.Yes,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()


class host(QWidget, uis_pack.main_ui):
    # окно, управляющее всеми другими
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.logo_label.setPixmap(QPixmap('QuestMaker1.png'))
        self.start_button.clicked.connect(self.start_game)
        self.change_button.clicked.connect(self.open_game)
        self.create_button.clicked.connect(self.create_game)

    def start_game(self):
        base_name = QFileDialog.getOpenFileName(self, 'Выбрать базу с игрой', '', 'База данных (*.db)')[0]
        if not self.check_table(base_name):
            return None
        if not base_name:
            return None
        pg = PageView(self, base_name=base_name)
        pg.exec_()

    def create_game(self):
        gc = game_creator(self)
        gc.exec_()

    def open_game(self):
        base_name = QFileDialog.getOpenFileName(self, 'Выбрать базу с игрой', '', 'База данных (*.db)')[0]
        if not self.check_table(base_name):
            return None
        if not base_name:
            return None
        mep = main_edit_page(self, base_name=base_name)
        mep.exec_()

    def sqlite_table_schema(self, conn, name):
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE name=?;", [name])
        sql = cursor.fetchone()[0]
        cursor.close()
        return sql

    def check_table(self, basename):
        con = sqlite3.connect(basename)
        cursor = con.cursor()
        right_tables = ['buttons', 'buttons_to_screens', 'description', 'screens']
        right_hashes = ['''CREATE TABLE buttons (
                id         INTEGER PRIMARY KEY
                                   UNIQUE
                                   NOT NULL,
                text       TEXT    NOT NULL,
                link       INTEGER REFERENCES screens (id),
                is_restart BOOLEAN NOT NULL
            )''',
                        '''CREATE TABLE buttons_to_screens (
            button_id INTEGER REFERENCES buttons (id) 
                              NOT NULL,
            screen_id INTEGER REFERENCES screens (id) 
                              NOT NULL
        )''',
                        '''CREATE TABLE description (
            name STRING NOT NULL
        )''',
                        '''CREATE TABLE screens (
            id    INTEGER PRIMARY KEY
                          NOT NULL,
            text  TEXT    NOT NULL,
            [key] TEXT    NOT NULL
                          UNIQUE
        )''']
        tables = sorted([i[0] for i in
                         cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
                         if i[0] != 'sqlite_sequence'])
        if right_tables == tables:
            for i in range(len(right_tables)):
                if self.sqlite_table_schema(con, right_tables[i]) != right_hashes[i]:
                    return False
            return True
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F1:
            text = '\tВ этом окне вы можете запустить игру для игрока и пройти один из созданных вами' + \
                   'или другими пользователями текстовый квест.\n\tТакже вы можете редактировать' + \
                   ' уже созданный квест или создать новый.'
            hw = help_window(self, text=text)
            hw.exec_()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    ex = host()
    ex.show()
    sys.exit(app.exec())

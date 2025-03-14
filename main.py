import telebot
import pandas as pd
import datetime
import schedule
import time
from telebot.types import Message, Document
import os
import config  # Импортируем файл с конфигурацией

# Токен бота
bot = telebot.TeleBot(config.TOKEN)

# Настройки
ADMIN_USER_ID = config.ADMIN_USER_ID  # ID пользователя, которому отправляется итоговое сообщение
SEMEN_USER_ID = config.SEMEN_USER_ID  # ID Семена
DEADLINE_TIME = config.DEADLINE_TIME  # Время окончания приема файлов
DEADLINE_DAY = config.DEADLINE_DAY    # День дедлайна (0 - понедельник, 6 - воскресенье)
UPLOAD_FOLDER = config.UPLOAD_FOLDER  # Папка для загруженных файлов

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Хранилище загруженных данных
data_storage = []


@bot.message_handler(content_types=['document'])
def handle_document(message: Message):
    """Обработчик загруженных файлов"""
    # Проверяем дедлайн
    now = datetime.datetime.now()
    if now.weekday() == DEADLINE_DAY and now.strftime("%H:%M") >= DEADLINE_TIME:
        bot.send_message(message.chat.id, "Вы опоздали!\nПишите в лс @V_V_K_101 или @SBO_good", parse_mode="HTML")
        return

    # Сохранение файла
    file_id = message.document.file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_path = os.path.join(UPLOAD_FOLDER, message.document.file_name)

    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # Обрабатываем файл
    process_file(file_path)
    bot.send_message(message.chat.id, "Файл принят. Спасибо!")


def process_file(file_path):
    """Функция обработки файла и сохранения данных"""
    xlsx_data = pd.ExcelFile(file_path)
    df = pd.read_excel(xlsx_data, sheet_name=xlsx_data.sheet_names[0])

    # Извлекаем данные начиная с 5-й строки
    df_data = df.iloc[4:, [2, 5, 6]].copy()  # Берем нужные столбцы
    df_data.columns = ['Проект', 'Имя ресурса', 'FTE']  # Переименовываем столбцы
    df_data = df_data.dropna(subset=['Проект', 'Имя ресурса', 'FTE'])  # Убираем пустые строки
    df_data['FTE'] = pd.to_numeric(df_data['FTE'], errors='coerce')  # Преобразуем FTE в число

    global data_storage
    data_storage.append(df_data)


def send_summary():
    """Формирование и отправка итогового сообщения"""
    if not data_storage:
        bot.send_message(ADMIN_USER_ID, "На этой неделе заявок не поступило.")
        print("[INFO] Сообщение: На этой неделе заявок не поступило.")
        return

    all_data = pd.concat(data_storage, ignore_index=True)
    grouped_data = all_data.groupby(['Проект', 'Имя ресурса'])['FTE'].sum().reset_index()

    message_text = "Доброе утро!\nОбщая заявка от Проектной группы:\n\n"
    current_project = None

    for _, row in grouped_data.iterrows():
        project = row['Проект']
        resource = row['Имя ресурса']
        fte = str(row['FTE']).replace('.', ',')

        if current_project != project:
            if current_project is not None:
                message_text += "\n"  # Добавляем пустую строку между проектами
            message_text += f"<b>{project}</b>\n"
            current_project = project
        message_text += f"{resource} - <i>{fte}</i>\n"

    print(f"[INFO] Отправляем сообщение: \n{message_text}")
    try:
        bot.send_message(ADMIN_USER_ID, message_text, parse_mode='HTML')
    except Exception as e:
        print(f"[ERROR] Ошибка при отправке сообщения: {e}")

    data_storage.clear()


# Планирование отправки сообщения каждую пятницу в 16:00
schedule.every().friday.at(DEADLINE_TIME).do(send_summary)


def schedule_checker():
    """Функция для выполнения запланированных задач"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверяем расписание каждую минуту


if __name__ == "__main__":
    import threading

    # Запускаем планировщик в отдельном потоке
    schedule_thread = threading.Thread(target=schedule_checker, daemon=True)
    schedule_thread.start()

    bot.polling(none_stop=True)
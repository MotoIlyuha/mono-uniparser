import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import time
import webbrowser
import socket

class ServerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Управление сервером Unipaser")
        self.geometry("800x600")

        self.server_process = None
        self.server_ready = False
        self.client_process = None

        self.create_widgets()

    def create_widgets(self):
        # Логи сервера
        self.log_frame = tk.LabelFrame(self, text="Логи сервера", padx=10, pady=10)
        self.log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.log_display = scrolledtext.ScrolledText(self.log_frame, state='disabled', width=80, height=25, bg="black", fg="white", font=("Courier New", 10))
        self.log_display.pack(fill=tk.BOTH, expand=True)

        # Кнопки управления
        self.button_frame = tk.Frame(self)
        self.button_frame.pack(pady=10)

        self.start_button = tk.Button(self.button_frame, text="Запустить сервер", command=self.start_server)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.open_parser_button = tk.Button(self.button_frame, text="Открыть парсер", command=self.open_parser_client, state=tk.DISABLED)
        self.open_parser_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.button_frame, text="Остановить сервер", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

    def update_log(self, message):
        self.log_display.configure(state='normal')
        self.log_display.insert(tk.END, message)
        self.log_display.see(tk.END) # Автоматическая прокрутка к последней строке
        self.log_display.configure(state='disabled')

    def run_server_command(self):
        server_executable = os.path.join("server", "dist", "server.exe")

        if not os.path.exists(server_executable):
            self.update_log(f"Ошибка: Исполняемый файл сервера не найден по пути: {server_executable}\n")
            messagebox.showerror("Ошибка", "Не найден исполняемый файл сервера. Убедитесь, что сервер собран с помощью PyInstaller.")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            return

        command = [server_executable]
        self.update_log(f"Запуск сервера командой: {' '.join(command)}\n")

        try:
            # Запускаем сервер в фоновом режиме и перенаправляем вывод
            self.server_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Объединяем stderr с stdout
                text=True, # Важно для чтения текстового вывода
                bufsize=1, # Буферизация по строкам
                universal_newlines=True, # Аналогично text=True
                encoding='utf-8', # Указываем кодировку
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 # Скрываем консольное окно на Windows
            )

            # Отслеживаем вывод сервера в отдельном потоке
            def read_output():
                for line in self.server_process.stdout:
                    self.update_log(line)
                    if "Running on http://127.0.0.1:5000" in line or "Running on http://0.0.0.0:5000" in line:
                        self.after(100, self.check_server_startup) # Проверяем запуск сервера после небольшой задержки
                self.server_process.wait() # Дожидаемся завершения процесса
                self.after(0, self.on_server_exit) # Выполняем в основном потоке GUI

            threading.Thread(target=read_output, daemon=True).start()

        except Exception as e:
            self.update_log(f"Ошибка при запуске сервера: {e}\n")
            messagebox.showerror("Ошибка", f"Не удалось запустить сервер: {e}")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def start_server(self):
        if self.server_process and self.server_process.poll() is None:
            messagebox.showinfo("Информация", "Сервер уже запущен.")
            return

        self.start_button.config(state=tk.DISABLED)
        self.open_parser_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.update_log("Попытка запустить сервер...\n")
        threading.Thread(target=self.run_server_command, daemon=True).start()

    def check_server_startup(self):
        # Проверяем, слушает ли сервер порт 5000
        host = "127.0.0.1"
        port = 5000
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1) # Таймаут 1 секунда
        try:
            sock.connect((host, port))
            sock.close()
            self.server_ready = True
            self.open_parser_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.NORMAL)
            self.update_log("Сервер успешно запущен на http://127.0.0.1:5000\n")
        except (socket.timeout, ConnectionRefusedError):
            self.server_ready = False
            self.open_parser_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.after(1000, self.check_server_startup) # Повторяем проверку через 1 секунду
        finally:
            sock.close()


    def stop_server(self):
        if self.server_process and self.server_process.poll() is None:
            self.update_log("Попытка остановить сервер...\n")
            try:
                self.server_process.terminate() # Мягкое завершение
                self.server_process.wait(timeout=5) # Ждем 5 секунд
                if self.server_process.poll() is None:
                    self.server_process.kill() # Если не завершился, принудительно убиваем
                self.update_log("Сервер остановлен.\n")
            except Exception as e:
                self.update_log(f"Ошибка при остановке сервера: {e}\n")
            finally:
                self.server_process = None
                self.server_ready = False
                self.start_button.config(state=tk.NORMAL)
                self.open_parser_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.DISABLED)
        else:
            messagebox.showinfo("Информация", "Сервер не запущен.")
            self.start_button.config(state=tk.NORMAL)
            self.open_parser_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)

    def on_server_exit(self):
        self.server_process = None
        self.server_ready = False
        self.update_log("Сервер завершил работу.\n")
        self.start_button.config(state=tk.NORMAL)
        self.open_parser_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)

    def open_parser_client(self):
        if self.client_process and self.client_process.poll() is None:
            self.update_log("Клиентское приложение уже запущено.\n")
            webbrowser.open("http://localhost:5001")
            return

        client_path = os.path.join("client", "dist")
        if not os.path.exists(client_path):
            self.update_log(f"Ошибка: Папка клиента не найдена по пути: {client_path}\n")
            messagebox.showerror("Ошибка", "Не найдена папка с собранным клиентским приложением. Убедитесь, что клиент собран с помощью npm run build.")
            return

        try:
            self.update_log("Запуск клиентского приложения...\n")
            self.client_process = subprocess.Popen(
                ["serve", client_path, "-p", "5001"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            # Даем серверу немного времени на запуск
            time.sleep(2)
            client_url = "http://localhost:5001"
            webbrowser.open(client_url)
            self.update_log(f"Открытие клиентского приложения в браузере: {client_url}\n")

            def read_client_output():
                for line in self.client_process.stdout:
                    self.update_log(f"[Client Serve] {line}")
                self.client_process.wait()
                self.update_log("Клиентский сервер завершил работу.\n")
                self.client_process = None
            threading.Thread(target=read_client_output, daemon=True).start()

        except Exception as e:
            self.update_log(f"Ошибка при запуске клиентского приложения: {e}\n")
            messagebox.showerror("Ошибка", f"Не удалось запустить клиентское приложение: {e}")

    def on_closing(self):
        if self.server_process and self.server_process.poll() is None:
            if messagebox.askyesno("Выход", "Сервер все еще запущен. Вы хотите остановить его и выйти?"):
                self.stop_server()
                if self.client_process and self.client_process.poll() is None:
                    self.client_process.terminate()
                    self.client_process.wait(timeout=5)
                self.destroy()
            else:
                pass
        else:
            if self.client_process and self.client_process.poll() is None:
                if messagebox.askyesno("Выход", "Клиентский сервер все еще запущен. Вы хотите остановить его и выйти?"):
                    self.client_process.terminate()
                    self.client_process.wait(timeout=5)
                    self.destroy()
                else:
                    pass
            else:
                self.destroy()

if __name__ == '__main__':
    app = ServerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop() 
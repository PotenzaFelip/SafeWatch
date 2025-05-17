import cv2
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import threading
import os
import shutil

def resize_with_aspect_ratio(frame, width=None, height=None):
    h, w = frame.shape[:2]
    if width is None and height is None:
        return frame
    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)
    else:
        r = width / float(w)
        dim = (width, int(h * r))
    return cv2.resize(frame, dim)

class CameraApp:
    def __init__(self, rtsp_url, window_width=1280, window_height=720):
        self.rtsp_url = rtsp_url
        self.window_width = window_width
        self.window_height = window_height

        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            raise Exception("Erro ao abrir o stream da câmera")

        self.root = tk.Tk()
        self.root.title("Camera IP")
        self.root.bind('<Key>', self.check_key)

        self.canvas = tk.Canvas(self.root, width=self.window_width, height=self.window_height, highlightthickness=0)
        self.canvas.pack()

        self.btn_screenshot = tk.Button(self.root, text="Tirar Print", command=self.take_screenshot, bg='gray20', fg='white', relief='flat', activebackground='gray40')
        self.btn_record = tk.Button(self.root, text="Gravar Vídeo", command=self.toggle_recording, bg='gray20', fg='white', relief='flat', activebackground='gray40')
        self.btn_save_buffer = tk.Button(self.root, text="Salvar últimos 20 min", command=self.save_last_20min, bg='gray20', fg='white', relief='flat', activebackground='gray40')

        self.canvas.create_window(400, 30, window=self.btn_screenshot)
        self.canvas.create_window(550, 30, window=self.btn_record)
        self.canvas.create_window(700, 30, window=self.btn_save_buffer)

        self.recording = False
        self.out = None
        self.fourcc = cv2.VideoWriter_fourcc(*'XVID')

        self.prev_time = 0
        self.retry_count = 0
        self.max_retries = 5

        self.buffer_duration_sec = 20 * 60
        self.fps = 20.0
        self.frame_size = (self.window_width, self.window_height)
        self.buffer_filename = "buffer_temp.avi"
        self.buffer_lock = threading.Lock()

        self.buffer_out = cv2.VideoWriter(self.buffer_filename, self.fourcc, self.fps, self.frame_size)

        self.update_frame()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def check_key(self, event):
        if event.char.lower() == 'q':
            self.on_closing()

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            print("Falha ao receber frame. Tentando reconectar...")
            self.cap.release()
            self.retry_count += 1
            if self.retry_count > self.max_retries:
                messagebox.showerror("Erro", "Não foi possível reconectar após várias tentativas.")
                self.root.destroy()
                return
            time.sleep(2)
            self.cap = cv2.VideoCapture(self.rtsp_url)
            self.root.after(10, self.update_frame)
            return

        self.retry_count = 0

        curr_time = time.time()
        fps = 1 / (curr_time - self.prev_time) if self.prev_time else 0
        self.prev_time = curr_time

        h, w = frame.shape[:2]
        cv2.putText(frame, f'FPS: {fps:.2f}', (w - 180, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        frame_resized = resize_with_aspect_ratio(frame, width=self.window_width, height=self.window_height)

        if self.recording and self.out is not None:
            frame_to_save = cv2.resize(frame_resized, self.frame_size)
            self.out.write(frame_to_save)

        frame_for_buffer = cv2.resize(frame_resized, self.frame_size)
        with self.buffer_lock:
            self.buffer_out.write(frame_for_buffer)

        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)

        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor='nw', image=imgtk)

        self.root.after(10, self.update_frame)

    def take_screenshot(self):
        ret, frame = self.cap.read()
        if ret:
            filename = f"screenshot_{int(time.time())}.png"
            cv2.imwrite(filename, frame)
            messagebox.showinfo("Print", f"Screenshot salva como {filename}")
        else:
            messagebox.showerror("Erro", "Falha ao capturar screenshot")

    def toggle_recording(self):
        if not self.recording:
            self.out = cv2.VideoWriter(f"gravacao_{int(time.time())}.avi",
                                       self.fourcc, self.fps, self.frame_size)
            self.recording = True
            self.btn_record.config(text="Parar Gravação")
        else:
            self.recording = False
            if self.out is not None:
                self.out.release()
                self.out = None
            self.btn_record.config(text="Gravar Vídeo")
            messagebox.showinfo("Gravação", "Vídeo salvo.")

    def save_last_20min(self):
        def salvar():
            with self.buffer_lock:
                self.buffer_out.release()
                timestamp = int(time.time())
                nome_final = f"ultimos_20min_{timestamp}.avi"
                shutil.copy(self.buffer_filename, nome_final)
                self.buffer_out = cv2.VideoWriter(self.buffer_filename, self.fourcc, self.fps, self.frame_size)
            messagebox.showinfo("Buffer Salvo", f"Últimos 20 minutos salvos em {nome_final}")

        threading.Thread(target=salvar).start()

    def on_closing(self):
        self.cap.release()
        if self.out is not None:
            self.out.release()
        with self.buffer_lock:
            self.buffer_out.release()
        self.root.destroy()

if __name__ == "__main__":
    arquivo_url = "rtsp_url.txt"
    if not os.path.exists(arquivo_url):
        print(f"Arquivo {arquivo_url} não encontrado. Crie o arquivo com a URL RTSP.")
        exit(1)

    with open(arquivo_url, "r") as f:
        rtsp_url = f.readline().strip()

    if not rtsp_url:
        print("Arquivo RTSP vazio. Insira uma URL válida.")
        exit(1)

    CameraApp(rtsp_url)

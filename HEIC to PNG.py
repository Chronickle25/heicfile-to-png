import os
import time
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

# Intentamos importar ttkbootstrap para estilos modernos; si no está disponible, usamos ttk estándar
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    import tkinter.ttk as ttk

# Intentamos importar PIL (Pillow)
try:
    from PIL import Image
except ImportError:
    messagebox.showerror("Error", "La librería Pillow es necesaria para ejecutar esta aplicación.")
    exit()

# Intentamos importar pillow_heif para manejar archivos HEIC
try:
    import pillow_heif
except ImportError:
    pillow_heif = None  # Si no está disponible, lo manejamos más adelante

class ImageConverterApp(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Conversor de Formatos de Imagen")
        self.master.geometry("600x350")
        self.master.resizable(True, True)

        # Aplicar estilo moderno con ttkbootstrap o estilo predeterminado
        try:
            self.style = ttk.Style(theme="cosmo")
        except:
            self.style = ttk.Style()
            self.style.theme_use('clam')

        self.create_widgets()

    def create_widgets(self):
        # Configuración de la cuadrícula principal
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Frame principal
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.columnconfigure(1, weight=1)

        # Etiqueta y campo de entrada para el directorio
        self.label_directory = ttk.Label(self.main_frame, text="Directorio de imágenes:")
        self.label_directory.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.entry_directory = ttk.Entry(self.main_frame)
        self.entry_directory.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.entry_directory.bind("<KeyRelease>", self.check_convert_button_state)

        self.button_browse = ttk.Button(self.main_frame, text="Examinar", command=self.select_directory)
        self.button_browse.grid(row=0, column=2, padx=5, pady=5)

        # Selección de formato de salida
        self.label_format = ttk.Label(self.main_frame, text="Formato de salida:")
        self.label_format.grid(row=1, column=0, padx=5, pady=5, sticky="e")

        self.format_combobox = ttk.Combobox(
            self.main_frame,
            values=["PNG", "JPEG", "BMP", "GIF", "TIFF"],
            state="readonly"
        )
        self.format_combobox.set("PNG")
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.format_combobox.bind("<<ComboboxSelected>>", self.toggle_quality_option)

        # Selección de calidad para JPEG
        self.label_quality = ttk.Label(self.main_frame, text="Calidad JPEG (1-100):")
        self.label_quality.grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.spin_quality = ttk.Spinbox(self.main_frame, from_=1, to=100, width=5)
        self.spin_quality.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.spin_quality.set(85)
        self.spin_quality.config(state=tk.DISABLED)

        # Botones de acción
        self.button_convert = ttk.Button(self.main_frame, text="Convertir", command=self.start_conversion, state=tk.DISABLED)
        self.button_convert.grid(row=3, column=0, padx=5, pady=10, sticky="e")

        self.button_cancel = ttk.Button(self.main_frame, text="Cancelar", command=self.cancel_conversion, state=tk.DISABLED)
        self.button_cancel.grid(row=3, column=1, padx=5, pady=10, sticky="w")

        # Barra de progreso
        self.progressbar = ttk.Progressbar(self.master, orient=tk.HORIZONTAL, mode='determinate')
        self.progressbar.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Etiquetas de estado
        self.completed_label = ttk.Label(self.master, text="Imágenes completadas: 0/0", anchor=tk.W)
        self.completed_label.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.status_label = ttk.Label(self.master, text="Listo para convertir.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Configuración adicional de columnas
        self.main_frame.columnconfigure(1, weight=1)
        self.master.columnconfigure(0, weight=1)

    def check_convert_button_state(self, event=None):
        directory = self.entry_directory.get().strip()
        if os.path.isdir(directory):
            self.button_convert.config(state=tk.NORMAL)
        else:
            self.button_convert.config(state=tk.DISABLED)

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_directory.delete(0, tk.END)
            self.entry_directory.insert(0, directory)
        self.check_convert_button_state()

    def toggle_quality_option(self, event=None):
        if self.format_combobox.get().strip().upper() == 'JPEG':
            self.spin_quality.config(state=tk.NORMAL)
        else:
            self.spin_quality.config(state=tk.DISABLED)

    def start_conversion(self):
        directory = self.entry_directory.get().strip()
        if not os.path.isdir(directory):
            messagebox.showerror("Error", "El directorio especificado no existe.")
            return

        output_format = self.format_combobox.get().strip().upper()
        if output_format not in ["PNG", "JPEG", "BMP", "GIF", "TIFF"]:
            messagebox.showerror("Error", "Formato de salida no válido.")
            return

        quality = int(self.spin_quality.get()) if output_format == 'JPEG' else 85

        self.button_convert.config(state=tk.DISABLED)
        self.button_cancel.config(state=tk.NORMAL)

        # Inicializar variables y eventos
        self.task_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.progressbar["value"] = 0
        self.status_label.config(text="Iniciando conversión...")
        self.completed = 0

        num_workers = self.calculate_optimal_workers()

        # Iniciar el hilo de procesamiento
        self.processing_thread = threading.Thread(
            target=self.process_files_in_parallel,
            args=(directory, output_format, num_workers, quality)
        )
        self.processing_thread.start()
        self.master.after(100, self.update_ui)

    def update_ui(self):
        try:
            while True:
                message = self.task_queue.get_nowait()
                if message['type'] == 'progress':
                    self.progressbar["value"] = message['value']
                    self.status_label.config(text=message['status'])
                    self.completed_label.config(text=f"Imágenes completadas: {message['completed']}/{message['total']}")
                elif message['type'] == 'done':
                    self.button_convert.config(state=tk.NORMAL)
                    self.button_cancel.config(state=tk.DISABLED)
                    self.status_label.config(text=message['status'])
                    return  # Detener la actualización después de completar
        except queue.Empty:
            pass

        if self.processing_thread.is_alive():
            self.master.after(100, self.update_ui)
        else:
            self.button_convert.config(state=tk.NORMAL)
            self.button_cancel.config(state=tk.DISABLED)

    def cancel_conversion(self):
        self.stop_event.set()
        self.status_label.config(text="Conversión cancelada.")
        self.button_cancel.config(state=tk.DISABLED)

    def process_files_in_parallel(self, directory, output_format, num_workers, quality):
        output_directory = self.create_output_directory(directory)
        image_files = self.get_image_files(directory)
        if not image_files:
            messagebox.showinfo("Información", "No se encontraron archivos de imagen en el directorio especificado.")
            self.task_queue.put({'type': 'done', 'status': 'No se encontraron imágenes.'})
            return

        total_files = len(image_files)
        self.progressbar["maximum"] = total_files

        successful_conversions = 0
        failed_conversions = 0

        start_time = time.time()

        with threading.Semaphore(num_workers) as pool:
            threads = []
            for filepath in image_files:
                if self.stop_event.is_set():
                    break
                thread = threading.Thread(
                    target=self.threaded_convert_image,
                    args=(filepath, output_directory, output_format, quality, total_files)
                )
                threads.append(thread)
                thread.start()

            # Esperar a que todos los hilos terminen
            for thread in threads:
                thread.join()

        if self.stop_event.is_set():
            self.task_queue.put({'type': 'done', 'status': 'Conversión cancelada.'})
            return

        total_time = time.time() - start_time
        time_str = time.strftime("%H:%M:%S", time.gmtime(total_time))
        summary = (f"Procesamiento completado en {time_str}.\n\n"
                   f"Éxitos: {successful_conversions}\n"
                   f"Fallos: {failed_conversions}")

        messagebox.showinfo("Resumen", summary)
        self.task_queue.put({'type': 'done', 'status': f"Conversión completada en {time_str}."})

    def threaded_convert_image(self, filepath, output_directory, output_format, quality, total_files):
        if self.stop_event.is_set():
            return

        success, message = self.convert_image(filepath, output_directory, output_format, quality)
        self.completed += 1
        status_text = f"Procesando: {os.path.basename(filepath)}"

        self.task_queue.put({
            'type': 'progress',
            'value': self.completed,
            'status': status_text,
            'completed': self.completed,
            'total': total_files
        })

    def convert_image(self, filepath, output_directory, output_format, quality=85):
        if self.stop_event.is_set():
            return False, "Proceso cancelado"

        filename = os.path.basename(filepath)
        new_filename = os.path.splitext(filename)[0] + f".{output_format.lower()}"
        new_filepath = os.path.join(output_directory, new_filename)

        try:
            if filepath.lower().endswith(".heic"):
                if pillow_heif is None:
                    return False, "La librería pillow_heif no está instalada."
                heif_file = pillow_heif.read_heif(filepath)
                image = Image.frombytes(
                    heif_file.mode, heif_file.size, heif_file.data, "raw"
                )
            else:
                image = Image.open(filepath)

            if output_format == 'JPEG':
                image.save(new_filepath, format=output_format, quality=quality)
            else:
                image.save(new_filepath, format=output_format)

            return True, f"Imagen guardada como: {new_filepath}"
        except Exception as e:
            return False, f"Error al convertir {filename}: {e}"

    def create_output_directory(self, directory):
        output_directory = os.path.join(directory, 'converted_images')
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        return output_directory

    def get_image_files(self, directory):
        valid_extensions = ['.heic', '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff']
        return [
            os.path.join(directory, filename)
            for filename in os.listdir(directory)
            if os.path.splitext(filename)[1].lower() in valid_extensions
        ]

    def calculate_optimal_workers(self):
        num_cores = os.cpu_count()
        return max(1, num_cores // 2)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageConverterApp(master=root)
    app.mainloop()

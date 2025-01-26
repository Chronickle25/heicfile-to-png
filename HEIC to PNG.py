import os
import time
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Intentamos importar ttkbootstrap para estilos modernos
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    from ttkbootstrap.tooltip import ToolTip
except ImportError:
    import tkinter.ttk as ttk

# Intentamos importar PIL (Pillow)
try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    messagebox.showerror("Error", "La librería Pillow es necesaria para ejecutar esta aplicación.")
    exit()

# Intentamos importar pillow_heif para manejar archivos HEIC
try:
    import pillow_heif
except ImportError:
    pillow_heif = None

class ImageConverterApp(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Conversor de Formatos de Imagen")
        self.master.geometry("720x450")
        self.master.resizable(True, True)
        self.setup_style()
        self.create_widgets()
        self.running = False

    def setup_style(self):
        try:
            self.style = ttk.Style(theme="morph")
            self.style.configure("TButton", padding=6)
            self.style.configure("Title.TLabel", font=('Helvetica', 12, 'bold'))
        except:
            self.style = ttk.Style()
            self.style.theme_use('clam')

    def create_widgets(self):
        # Configuración de la cuadrícula principal
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Frame principal con padding y expansión
        main_frame = ttk.Frame(self.master, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)

        # Sección de selección de directorio
        dir_frame = ttk.LabelFrame(main_frame, text=" Directorio de origen ", padding=10)
        dir_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        
        self.entry_directory = ttk.Entry(dir_frame)
        self.entry_directory.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_directory.bind("<KeyRelease>", self.check_convert_button_state)
        
        browse_btn = ttk.Button(dir_frame, text="Examinar", command=self.select_directory, width=10)
        browse_btn.pack(side=tk.RIGHT)

        # Sección de configuración de conversión
        config_frame = ttk.LabelFrame(main_frame, text=" Configuración de conversión ", padding=10)
        config_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

        # Selección de formato
        ttk.Label(config_frame, text="Formato de salida:").grid(row=0, column=0, sticky="e", padx=5)
        self.format_combobox = ttk.Combobox(
            config_frame,
            values=["PNG", "JPEG", "BMP", "GIF", "TIFF"],
            state="readonly",
            width=8
        )
        self.format_combobox.set("PNG")
        self.format_combobox.grid(row=0, column=1, sticky="w", padx=5)
        self.format_combobox.bind("<<ComboboxSelected>>", self.toggle_quality_option)

        # Configuración de calidad
        self.quality_frame = ttk.Frame(config_frame)
        self.quality_frame.grid(row=0, column=2, sticky="w", padx=20)
        ttk.Label(self.quality_frame, text="Calidad:").pack(side=tk.LEFT)
        self.quality_scale = ttk.Scale(self.quality_frame, from_=1, to=100, value=85, length=120)
        self.quality_scale.pack(side=tk.LEFT, padx=5)
        self.quality_value = ttk.Label(self.quality_frame, text="85")
        self.quality_value.pack(side=tk.LEFT)
        self.quality_scale.configure(command=lambda v: self.quality_value.config(text=f"{float(v):.0f}"))
        self.quality_frame.pack_forget()

        # Sección de progreso
        progress_frame = ttk.LabelFrame(main_frame, text=" Progreso ", padding=10)
        progress_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        self.progressbar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progressbar.pack(fill=tk.X, expand=True)
        
        self.status_label = ttk.Label(progress_frame, text="Listo para comenzar", anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=(5,0))
        
        self.details_label = ttk.Label(progress_frame, text="", anchor=tk.W)
        self.details_label.pack(fill=tk.X)

        # Botones de control
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.btn_convert = ttk.Button(
            btn_frame, 
            text="Iniciar conversión", 
            command=self.start_conversion, 
            state=tk.DISABLED,
            bootstyle="success"
        )
        self.btn_convert.pack(side=tk.LEFT, padx=5)
        
        self.btn_cancel = ttk.Button(
            btn_frame, 
            text="Cancelar", 
            command=self.cancel_conversion, 
            state=tk.DISABLED,
            bootstyle="danger"
        )
        self.btn_cancel.pack(side=tk.LEFT, padx=5)

        # Tooltips
        if 'ToolTip' in globals():
            ToolTip(self.btn_convert, text="Inicia el proceso de conversión de imágenes")
            ToolTip(self.btn_cancel, text="Cancela la conversión en curso")

    def toggle_quality_option(self, event=None):
        if self.format_combobox.get() == 'JPEG':
            self.quality_frame.grid()
        else:
            self.quality_frame.grid_remove()

    def check_convert_button_state(self, event=None):
        directory = self.entry_directory.get().strip()
        self.btn_convert['state'] = tk.NORMAL if os.path.isdir(directory) else tk.DISABLED

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_directory.delete(0, tk.END)
            self.entry_directory.insert(0, directory)
            self.check_convert_button_state()

    def start_conversion(self):
        directory = self.entry_directory.get().strip()
        if not os.path.isdir(directory):
            messagebox.showerror("Error", "Directorio no válido")
            return

        self.running = True
        self.btn_convert['state'] = tk.DISABLED
        self.btn_cancel['state'] = tk.NORMAL
        self.progressbar['value'] = 0

        output_format = self.format_combobox.get().upper()
        quality = int(float(self.quality_scale.get())) if output_format == 'JPEG' else 85

        self.stop_event = threading.Event()
        self.task_queue = queue.Queue()
        self.success_count = 0
        self.failed_count = 0

        processing_thread = threading.Thread(
            target=self.process_images,
            args=(directory, output_format, quality),
            daemon=True
        )
        processing_thread.start()
        self.master.after(100, self.update_ui)

    def process_images(self, directory, output_format, quality):
        try:
            output_dir = self.create_output_directory(directory)
            files = self.get_image_files(directory)
            total_files = len(files)
            
            if not total_files:
                self.task_queue.put({'type': 'error', 'message': 'No se encontraron imágenes válidas'})
                return

            self.task_queue.put({'type': 'progress', 'total': total_files, 'current': 0})

            with ThreadPoolExecutor(max_workers=self.get_optimal_workers()) as executor:
                futures = {
                    executor.submit(
                        self.convert_image, 
                        filepath, 
                        output_dir, 
                        output_format, 
                        quality
                    ): filepath for filepath in files
                }

                for future in as_completed(futures):
                    if self.stop_event.is_set():
                        break
                    
                    success, message = future.result()
                    if success:
                        self.success_count += 1
                    else:
                        self.failed_count += 1
                    
                    self.task_queue.put({
                        'type': 'progress',
                        'total': total_files,
                        'current': self.success_count + self.failed_count,
                        'file': os.path.basename(futures[future]),
                        'success': success,
                        'message': message
                    })

        except Exception as e:
            self.task_queue.put({'type': 'error', 'message': f"Error general: {str(e)}"})
        finally:
            self.task_queue.put({'type': 'done'})

    def convert_image(self, filepath, output_dir, output_format, quality):
        if self.stop_event.is_set():
            return False, "Cancelado"

        try:
            filename = os.path.basename(filepath)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{base_name}.{output_format.lower()}")
            
            if filepath.lower().endswith('.heic'):
                if not pillow_heif:
                    return False, "HEIC no soportado (instalar pillow_heif)"
                heif_file = pillow_heif.read_heif(filepath)
                image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
            else:
                with Image.open(filepath) as image:
                    save_args = {'format': output_format}
                    if output_format == 'JPEG':
                        save_args['quality'] = quality
                        if image.mode in ('RGBA', 'LA'):
                            image = image.convert('RGB')
                    image.save(output_path, **save_args)
            
            return True, f"Convertido: {filename}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def update_ui(self):
        try:
            while not self.task_queue.empty():
                task = self.task_queue.get_nowait()
                
                if task['type'] == 'progress':
                    self.progressbar['maximum'] = task['total']
                    self.progressbar['value'] = task['current']
                    self.status_label.config(text=f"Procesando: {task.get('file', '')}")
                    status_text = f"Completadas: {task['current']}/{task['total']} | "
                    status_text += f"Éxitos: {self.success_count} | Fallos: {self.failed_count}"
                    self.details_label.config(text=status_text)
                
                elif task['type'] == 'error':
                    messagebox.showerror("Error", task['message'])
                
                elif task['type'] == 'done':
                    self.conversion_complete()

        except queue.Empty:
            pass

        if self.running:
            self.master.after(100, self.update_ui)

    def conversion_complete(self):
        self.running = False
        self.btn_convert['state'] = tk.NORMAL
        self.btn_cancel['state'] = tk.DISABLED
        self.status_label.config(text="Conversión completada" if not self.stop_event.is_set() else "Conversión cancelada")
        
        if not self.stop_event.is_set():
            messagebox.showinfo(
                "Resumen",
                f"Conversión finalizada:\n\nÉxitos: {self.success_count}\nFallos: {self.failed_count}"
            )

    def cancel_conversion(self):
        self.stop_event.set()
        self.running = False
        self.btn_cancel['state'] = tk.DISABLED
        self.status_label.config(text="Cancelando...")

    def create_output_directory(self, base_dir):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(base_dir, f"converted_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_image_files(self, directory):
        valid_extensions = {'.heic', '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif'}
        return [
            os.path.join(directory, f) for f in os.listdir(directory)
            if os.path.splitext(f)[1].lower() in valid_extensions
            and os.path.isfile(os.path.join(directory, f))
        ]

    def get_optimal_workers(self):
        return max(1, os.cpu_count() // 2)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageConverterApp(root)
    root.mainloop()
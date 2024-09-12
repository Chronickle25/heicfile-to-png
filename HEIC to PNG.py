import os
import time
import psutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import pillow_heif
from concurrent.futures import ThreadPoolExecutor, as_completed

class ImageConverterApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.geometry("600x220")
        self.master.resizable(False, False)  # Deshabilita maximización
        self.master.title("Conversor de Formatos de Imagen")

        # Aplicar estilo moderno con ttk
        style = ttk.Style()
        style.theme_use('clam')

        self.create_widgets()

    def create_widgets(self):
        # Frame para seleccionar el directorio
        self.frame_top = ttk.Frame(self.master)
        self.frame_top.pack(padx=10, pady=10, fill=tk.X)

        # Etiqueta y campo de entrada para directorio
        self.label_directory = ttk.Label(self.frame_top, text="Directorio de imágenes:")
        self.label_directory.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.entry_directory = ttk.Entry(self.frame_top, width=50)
        self.entry_directory.grid(row=0, column=1, padx=5, pady=5)
        self.entry_directory.bind("<KeyRelease>", self.check_convert_button_state)

        self.button_browse = ttk.Button(self.frame_top, text="Examinar", command=self.select_directory)
        self.button_browse.grid(row=0, column=2, padx=5, pady=5)

        # Formato de salida y calidad
        self.label_format = ttk.Label(self.frame_top, text="Formato de salida:")
        self.label_format.grid(row=1, column=0, padx=5, pady=5, sticky="e")

        self.format_combobox = ttk.Combobox(self.frame_top, values=["PNG", "JPEG", "BMP", "GIF", "TIFF"], state="readonly")
        self.format_combobox.set("PNG")
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5)
        self.format_combobox.bind("<<ComboboxSelected>>", self.toggle_quality_option)

        self.label_quality = ttk.Label(self.frame_top, text="Calidad JPEG (1-100):")
        self.label_quality.grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.spin_quality = ttk.Spinbox(self.frame_top, from_=1, to=100, width=5)
        self.spin_quality.grid(row=2, column=1, padx=5, pady=5)
        self.spin_quality.set(85)
        self.spin_quality.config(state=tk.DISABLED)

        # Botones
        self.frame_buttons = ttk.Frame(self.master)
        self.frame_buttons.pack(pady=10)

        self.button_convert = ttk.Button(self.frame_buttons, text="Convertir", command=self.start_conversion, state=tk.DISABLED)
        self.button_convert.grid(row=0, column=0, padx=20)

        self.button_cancel = ttk.Button(self.frame_buttons, text="Cancelar", command=self.cancel_conversion, state=tk.DISABLED)
        self.button_cancel.grid(row=0, column=1, padx=20)

        # Etiquetas de estado en la misma línea
        self.frame_status = ttk.Frame(self.master)
        self.frame_status.pack(fill=tk.X)

        self.completed_label = ttk.Label(self.frame_status, text="Imágenes completadas: 0/0", relief=tk.SUNKEN, anchor=tk.W)
        self.completed_label.grid(row=0, column=0, padx=5, pady=5)

        self.status_label = ttk.Label(self.frame_status, text="Listo para convertir.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        self.progressbar = ttk.Progressbar(self.master, orient=tk.HORIZONTAL, mode='determinate', length=580)

    # Función para verificar si el botón de convertir debe estar habilitado
    def check_convert_button_state(self, event=None):
        if self.entry_directory.get().strip():
            self.button_convert.config(state=tk.NORMAL)
        else:
            self.button_convert.config(state=tk.DISABLED)

    # Funciones principales
    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_directory.delete(0, tk.END)
            self.entry_directory.insert(0, directory)
        self.check_convert_button_state()

    def toggle_quality_option(self, event):
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
        if output_format not in ["HEIC", "PNG", "JPEG", "BMP", "GIF", "TIFF"]:
            messagebox.showerror("Error", "Formato de salida no válido.")
            return

        num_workers = self.calculate_optimal_workers()
        quality = int(self.spin_quality.get()) if output_format == 'JPEG' else 85

        self.button_convert.config(state=tk.DISABLED)
        self.button_cancel.config(state=tk.NORMAL)

        self.process_files_in_parallel(directory, output_format, num_workers, quality)

        self.button_convert.config(state=tk.NORMAL)
        self.button_cancel.config(state=tk.DISABLED)

    def cancel_conversion(self):
        global running
        running = False
        self.status_label.config(text="Conversión cancelada.")

    def process_files_in_parallel(self, directory, output_format, num_workers, quality):
        global running
        running = True
        output_directory = self.create_output_directory(directory)
        image_files = self.get_image_files(directory)
        if not image_files:
            messagebox.showinfo("Información", "No se encontraron archivos de imagen en el directorio especificado.")
            return

        self.progressbar["maximum"] = len(image_files)
        self.progressbar["value"] = 0
        self.progressbar.pack(pady=10)

        successful_conversions = 0
        failed_conversions = 0

        self.status_label.config(text="Iniciando conversión...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_file = {executor.submit(self.convert_image, filepath, output_directory, output_format, quality): filepath for filepath in image_files}
            for i, future in enumerate(as_completed(future_to_file), start=1):
                if not running:
                    break
                try:
                    success, message = future.result()
                    self.status_label.config(text=f"Procesando: {os.path.basename(future_to_file[future])}")
                    self.progressbar["value"] += 1
                    self.completed_label.config(text=f"Imágenes completadas: {i}/{len(image_files)}")
                    self.master.update_idletasks()
                    if success:
                        successful_conversions += 1
                    else:
                        failed_conversions += 1
                except Exception as e:
                    self.status_label.config(text=f"Error procesando archivo: {e}")

        total_time = time.time() - start_time
        time_str = time.strftime("%H:%M:%S", time.gmtime(total_time))

        self.progressbar.pack_forget()
        summary = (f"Procesamiento completado en {time_str}.\n\n"
                   f"Éxitos: {successful_conversions}\n"
                   f"Fallos: {failed_conversions}")
        messagebox.showinfo("Resumen", summary)
        self.status_label.config(text=f"Conversión completada en {time_str}.")

    def get_image_files(self, directory):
        valid_extensions = ['.heic', '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff']
        return [os.path.join(directory, filename) for filename in os.listdir(directory) if os.path.splitext(filename)[1].lower() in valid_extensions]

    def create_output_directory(self, directory):
        output_directory = os.path.join(directory, 'converted_images')
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        return output_directory

    def convert_image(self, filepath, output_directory, output_format, quality=85):
        filename = os.path.basename(filepath)
        new_filename = os.path.splitext(filename)[0] + f".{output_format.lower()}"
        new_filepath = os.path.join(output_directory, new_filename)

        try:
            if filepath.lower().endswith(".heic"):
                # Si es HEIC, convertir desde HEIC a otros formatos
                heif_file = pillow_heif.read_heif(filepath)
                image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
            else:
                # Si es otro formato, abrir con PIL y convertir a HEIC o el formato seleccionado
                image = Image.open(filepath)
            
            # Guardar la imagen en el formato seleccionado
            if output_format == 'JPEG':
                image.save(new_filepath, format=output_format, quality=quality)
            else:
                image.save(new_filepath, format=output_format)
            return True, f"Imagen guardada como: {new_filepath}"
        except Exception as e:
            return False, f"Error al convertir {filename}: {e}"

    def calculate_optimal_workers(self):
        num_cores = os.cpu_count()
        cpu_usage = psutil.cpu_percent(interval=1)
        return max(1, num_cores // 2 if cpu_usage > 75 else num_cores)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageConverterApp(master=root)
    app.mainloop()

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .config import APP_TITLE, DEFAULT_K
from .gis_pipeline import run_pipeline

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x620")

        self.k_var = tk.StringVar(value=str(DEFAULT_K))
        self.out_var = tk.StringVar(value="")

        self._img_ref = None
        self._last_run_dir = None
        self._last_report = None

        self._build()

    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        row = ttk.Frame(root)
        row.pack(fill="x")

        ttk.Label(row, text="k (power > 1):").pack(side="left")
        ttk.Entry(row, textvariable=self.k_var, width=8).pack(side="left", padx=(6, 18))

        ttk.Label(row, text="Output folder:").pack(side="left")
        ttk.Entry(row, textvariable=self.out_var).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row, text="Browse", command=self.pick_output_folder).pack(side="left")

        self.run_btn = ttk.Button(row, text="Run", command=self.run_clicked)
        self.run_btn.pack(side="left", padx=(10, 0))

        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(10, 10))
        self.progress["value"] = 0

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=320)
        left.pack(side="left", fill="y", expand=False, padx=(0, 10))
        left.pack_propagate(False)  # keep left fixed width

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Status:").pack(anchor="w")
        self.log_box = tk.Text(left, height=10, wrap="word")
        self.log_box.pack(fill="both", expand=False, pady=(6, 0))
        self.log_box.configure(state="disabled")

        ttk.Label(left, text="Regression Scatter:").pack(anchor="w", pady=(10, 0))
        self.scatter_label = ttk.Label(left)
        self.scatter_label.pack(fill="both", expand=True, pady=(6, 0))

        ttk.Label(right, text="Map Preview (PNG):").pack(anchor="w")
        self.map_label = ttk.Label(right)
        self.map_label.pack(fill="both", expand=True, pady=(6, 10))

        self.open_out_btn = ttk.Button(right, text="Open Output Folder", command=self.open_output, state="disabled")
        self.open_out_btn.pack(fill="x")

        self.open_rep_btn = ttk.Button(right, text="Open Regression Report", command=self.open_report, state="disabled")
        self.open_rep_btn.pack(fill="x", pady=(6, 0))

    def log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update_idletasks()

    def pick_output_folder(self):
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.out_var.set(p)

    def run_clicked(self):
        try:
            k = float(self.k_var.get().strip())
        except Exception:
            messagebox.showerror("Invalid k", "k must be a number (example: 2.0).")
            return

        out_base = self.out_var.get().strip()
        if not out_base:
            messagebox.showerror("Missing output folder", "Pick an output folder.")
            return

        self.run_btn.configure(state="disabled")
        self.open_out_btn.configure(state="disabled")
        self.open_rep_btn.configure(state="disabled")
        self.log("Starting pipeline...")

        def worker():
            try:
                self.after(0, lambda: self.progress.configure(value=5))
                result = run_pipeline(
                    k=k,
                    out_base=out_base,
                    log=self.log,
                    progress_callback=lambda pct: self.after(
                        0, lambda: self.progress.configure(value=pct)
                    )
                )
                self._last_run_dir = result["run_dir"]
                self._last_report = result["regression_report"]
                self.after(0, lambda: self.update_preview(result["map_png"]))
                self.after(0, lambda: self.update_scatter_preview(result["scatter_png"]))
                self.after(0, lambda: self.open_out_btn.configure(state="normal"))
                self.after(0, lambda: self.open_rep_btn.configure(state="normal"))
                self.after(0, lambda: messagebox.showinfo("Complete", "Run finished."))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            finally:
                self.after(0, self.done)

        threading.Thread(target=worker, daemon=True).start()

    def update_preview(self, png_path: str):
        try:
            from PIL import Image, ImageTk

            img = Image.open(png_path)

            container_width = self.map_label.winfo_width()
            container_height = self.map_label.winfo_height()

            if container_width < 50 or container_height < 50:
                self.update_idletasks()
                container_width = self.map_label.winfo_width()
                container_height = self.map_label.winfo_height()

            max_width = container_width - 10
            max_height = container_height - 10

            img.thumbnail((max_width, max_height))

            tk_img = ImageTk.PhotoImage(img)

            self._img_ref = tk_img
            self.map_label.configure(image=tk_img)
            
            self.log("Preview updated.")

        except Exception as e:
            self.log(f"Preview error: {e}")


    def update_scatter_preview(self, png_path: str):
        try:
            from PIL import Image, ImageTk

            img = Image.open(png_path)

            w = self.scatter_label.winfo_width()
            h = self.scatter_label.winfo_height()
            if w < 50 or h < 50:
                self.update_idletasks()
                w = self.scatter_label.winfo_width()
                h = self.scatter_label.winfo_height()

            img.thumbnail((max(1, w - 10), max(1, h - 10)))

            tk_img = ImageTk.PhotoImage(img)
            self._scatter_img_ref = tk_img
            self.scatter_label.configure(image=tk_img)

            self.log("Scatter preview updated.")
        except Exception as e:
            self.log(f"Scatter preview error: {e}")

    def open_output(self):
        if self._last_run_dir and os.path.isdir(self._last_run_dir):
            os.startfile(self._last_run_dir)

    def open_report(self):
        if self._last_report and os.path.exists(self._last_report):
            os.startfile(self._last_report)

    def done(self):
        self.run_btn.configure(state="normal")
        self.log("Ready.")
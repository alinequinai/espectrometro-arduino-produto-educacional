# -*- coding: utf-8 -*-
"""Espectrômetro didático AS7341 — interface em roxo e lilás.

O Arduino deve enviar F1..F8 em CSV, a 115200 baud, aceitando vírgula final.
Os valores brutos na interface são exatamente os recebidos pela serial.
"""
import sys
import importlib.util
import subprocess


def instalar_se_necessario(pacote, modulo):
    # O executável contém suas próprias dependências; não tenta instalar nada.
    if not getattr(sys, "frozen", False) and importlib.util.find_spec(modulo) is None:
        print(f"Instalando biblioteca necessária: {pacote}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])


if __name__ == "__main__" or not getattr(sys, "frozen", False):
    instalar_se_necessario("pyserial", "serial")
    instalar_se_necessario("matplotlib", "matplotlib")
    instalar_se_necessario("numpy", "numpy")
    instalar_se_necessario("scipy", "scipy")

import csv
import math
import re
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import serial
from serial.tools import list_ports
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.interpolate import PchipInterpolator

# ------------------------------------------------------------------
# Dados do sensor e identidade visual
# ------------------------------------------------------------------
WAVELENGTHS = np.array([415, 445, 480, 515, 555, 590, 630, 680], dtype=float)
CHANNELS = [f"F{i}" for i in range(1, 9)]
NAMES = ["violeta", "azul", "ciano", "verde", "verde-amarelo", "amarelo", "vermelho", "vermelho profundo"]
COLORS = ["#7430BB", "#2456F2", "#18B7EA", "#0AC872", "#ADDB33", "#FFC536", "#FC373B", "#AC143A"]
# Coeficientes exploratórios: NÃO equivalem a uma calibração radiométrica.
FACTORS = np.array([1.2, 1.1, 1.0, 1.0, 0.9, 0.9, 1.1, 1.2], dtype=float)
BAUD = 115200
DARK_SAMPLES = 20
MIN_SIGNAL = 10  # Contagens acima do escuro para exibir intensidade normalizada.

BG = "#F7F2FF"
CARD = "#FFFFFF"
BORDER = "#DDD0F6"
INK = "#311258"
PURPLE = "#6528AD"
PURPLE_DARK = "#461483"
LILAC = "#F0E3FF"
MUTED = "#715B88"
GREEN = "#138A55"
RED = "#C74459"
FONT = "Segoe UI"


def resource_path(relative_path):
    """Resolve arquivos tanto no .py quanto no executável do PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / relative_path)
    return str(Path(__file__).resolve().parent / relative_path)




def parse_csv(line):
    """Aceita:
    1) 8 inteiros separados por vírgula, com ou sem vírgula final;
    2) formato de diagnóstico: F1=123 F2=456 ... F8=789
    """
    if not line:
        return None

    text = line.strip()
    if not text:
        return None

    # Formato CSV
    parts = text.split(",")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) == 8:
        try:
            values = [int(p.strip()) for p in parts]
            if all(0 <= v <= 65535 for v in values):
                return np.asarray(values, dtype=float)
        except ValueError:
            pass

    # Formato "F1=123 F2=456 ..."
    matches = re.findall(r"F\d\s*=\s*(\d+)", text)
    if len(matches) == 8:
        values = [int(v) for v in matches]
        if all(0 <= v <= 65535 for v in values):
            return np.asarray(values, dtype=float)

    return None


def processed_reading(raw, dark, correction=False):
    """Subtrai fundo, opcionalmente pondera canais e normaliza."""
    corrected = np.maximum(raw - dark, 0.0)
    if correction:
        corrected = corrected * FACTORS
    maximum = float(corrected.max())
    normalized = corrected / maximum if maximum >= MIN_SIGNAL else np.zeros(8)
    return corrected, normalized, maximum


def rounded_rect(canvas, x1, y1, x2, y2, r, fill, outline="", width=1):
    """Retângulo arredondado sem dependências gráficas extras."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r,
              x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
    return canvas.create_polygon(points, smooth=True, splinesteps=20,
                                 fill=fill, outline=outline, width=width)


class RoundButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=PURPLE, fg="white", hover=None,
                 width=155, height=43, disabled=False):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.command = command
        self.text = text
        self.base = bg
        self.fg = fg
        self.hover = hover or PURPLE_DARK
        self.disabled = disabled
        self.w = width
        self.h = height
        self.paint(False)
        self.bind("<Button-1>", self.click)
        self.bind("<Enter>", lambda e: self.paint(True))
        self.bind("<Leave>", lambda e: self.paint(False))

    def paint(self, hover=False):
        self.delete("all")
        fill = "#E9E3F0" if self.disabled else (self.hover if hover else self.base)
        foreground = "#A9A2B1" if self.disabled else self.fg
        rounded_rect(self, 1, 1, self.w - 1, self.h - 1, 19, fill)
        self.create_text(self.w/2, self.h/2, text=self.text, fill=foreground,
                         font=(FONT, 10, "bold"))
        self.configure(cursor="arrow" if self.disabled else "hand2")

    def click(self, _):
        if not self.disabled:
            self.command()

    def enable(self, enabled):
        self.disabled = not enabled
        self.paint(False)


class Card(tk.Canvas):
    """Cartão com borda e cantos arredondados; interior aceita widgets Tk."""
    def __init__(self, parent, background=CARD, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, **kwargs)
        self.card_bg = background
        self.body = tk.Frame(self, bg=background)
        self.window = self.create_window(12, 12, window=self.body, anchor="nw")
        self.bind("<Configure>", self._resize)

    def _resize(self, event):
        self.delete("shape")
        shape = rounded_rect(self, 2, 2, max(3, event.width - 3), max(3, event.height - 3),
                             16, self.card_bg, BORDER)
        self.addtag_withtag("shape", shape)
        self.tag_lower(shape)  # figura atrás do conteúdo
        self.coords(self.window, 13, 11)
        self.itemconfigure(self.window, width=max(1, event.width - 26),
                           height=max(1, event.height - 23))


def label(parent, text, size=10, weight="normal", color=INK, bg=None, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, weight), fg=color,
                    bg=bg or parent.cget("bg"), **kwargs)


class EspectrometroApp:
    def __init__(self, root):
        self.root = root
        root.title("Espectrometro AS7341 | Produto educacional")
        # Ajusta ao monitor do professor, inclusive notebooks menores.
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        win_w = min(1500, max(1090, screen_w - 36))
        win_h = min(900, max(690, screen_h - 75))
        root.geometry(f"{win_w}x{win_h}+12+10")
        root.minsize(1090, 690)
        root.configure(bg=BG)
        self.stop_event = threading.Event()
        self.events = queue.Queue(maxsize=50)
        self.thread = None
        self.running = False
        self.serial_port = None
        self.dark = np.zeros(8, dtype=float)
        self.last_raw = None
        self.last_corr = None
        self.last_norm = None
        self.last_update = 0
        self.has_signal = False
        self.calibration_done = False
        self.correction = tk.BooleanVar(value=False)
        self.graph_type = tk.StringVar(value="Apenas Barras")
        self.status_var = tk.StringVar(value="Aguardando conexão")
        self.port_var = tk.StringVar(value="")
        self._create_ui()
        self.detect_ports()
        self.root.after(100, self.consume_events)
        root.protocol("WM_DELETE_WINDOW", self.on_close)


    def draw_atom_logo(self, canvas, cx, cy, r, color):
        canvas.create_oval(cx-r*0.25, cy-r*0.25, cx+r*0.25, cy+r*0.25,
                           fill=color, outline=color)
        for angle in (0, 60, -60):
            rx = r
            ry = r * 0.42
            pts = []
            for t in range(0, 361, 8):
                tt = math.radians(t)
                x = rx * math.cos(tt)
                y = ry * math.sin(tt)
                aa = math.radians(angle)
                xr = x * math.cos(aa) - y * math.sin(aa)
                yr = x * math.sin(aa) + y * math.cos(aa)
                pts.extend([cx + xr, cy + yr])
            canvas.create_line(*pts, fill=color, width=2.2, smooth=True)

    def _create_ui(self):
        # Banner
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=21, pady=(11, 6))
        self.atom_logo = tk.Canvas(header, width=58, height=58, bg=BG, highlightthickness=0)
        self.atom_logo.pack(side="left", padx=(0, 11))
        self.draw_atom_logo(self.atom_logo, 29, 29, 23, PURPLE)
        heading = tk.Frame(header, bg=BG)
        heading.pack(side="left")
        label(heading, "Espectrômetro AS7341", 27, "bold", PURPLE_DARK).pack(anchor="w")
        label(heading, "Explorando a luz, revelando o espectro", 12, color=MUTED).pack(anchor="w")
        self.about_btn = RoundButton(header, "Sobre", self.show_about,
                                     width=126, bg=PURPLE)
        self.about_btn.pack(side="right", padx=3)
        label(header, "Ciência hoje, mais descobertas amanhã!", 12, "italic",
              PURPLE).pack(side="right", padx=25)

        # Top row of four cards
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=17, pady=(0, 7))
        for col, w in enumerate([35, 26, 22, 17]):
            top.grid_columnconfigure(col, weight=w, uniform="top")
        conn = Card(top, height=132)
        expt = Card(top, height=132)
        display = Card(top, height=132)
        opts = Card(top, height=132)
        for i, card in enumerate((conn, expt, display, opts)):
            card.grid(row=0, column=i, sticky="nsew", padx=3)

        label(conn.body, "Conexao com o Arduino", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(4, 10))
        cr = tk.Frame(conn.body, bg=CARD)
        cr.pack(fill="x")
        RoundButton(cr, "Detectar Arduino", self.detect_ports, width=155).pack(side="left", padx=(0, 7))
        cp = tk.Frame(cr, bg=CARD)
        cp.pack(side="left", fill="x", expand=True)
        label(cp, "Porta COM:", 9, color=MUTED).pack(anchor="w")
        self.portbox = ttk.Combobox(cp, textvariable=self.port_var, state="readonly", width=11)
        self.portbox.pack(anchor="w")
        label(conn.body, "Selecione a porta da sua placa.", 9, color=MUTED).pack(anchor="w", pady=(4, 0))

        label(expt.body, "Experimento", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(4, 10))
        er = tk.Frame(expt.body, bg=CARD)
        er.pack(anchor="w")
        self.start_btn = RoundButton(er, "Iniciar Experimento", self.start,
                                     width=175)
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = RoundButton(er, "Parar", self.stop, bg="#D64A66",
                                    hover="#B53453", width=90, disabled=True)
        self.stop_btn.pack(side="left")
        label(expt.body, "Tampe o sensor durante a calibração.", 9, color=MUTED).pack(anchor="w", pady=(8, 0))

        label(display.body, "Visualizacao", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(4, 4))
        for mode in ["Apenas Barras", "Apenas Curva", "Barras + Curva"]:
            tk.Radiobutton(display.body, text=mode, variable=self.graph_type, value=mode,
                           command=self.redraw, bg=CARD, fg=INK, activebackground=CARD,
                           selectcolor=LILAC, highlightthickness=0, font=(FONT, 10),
                           padx=1, pady=0).pack(anchor="w")

        label(opts.body, "Opcoes", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(4, 10))
        tk.Checkbutton(opts.body, text="Correção espectral", variable=self.correction,
                       command=self.redraw, bg=CARD, fg=INK, activebackground=CARD,
                       selectcolor=LILAC, highlightthickness=0,
                       font=(FONT, 9)).pack(anchor="w")
        label(opts.body, "Desativada por padrão", 9, "italic", MUTED).pack(anchor="w", padx=21)
        tk.Button(opts.body, text="O que e isso?", relief="flat", bg=CARD,
                  fg=PURPLE, font=(FONT, 9, "underline"), cursor="hand2",
                  command=self.show_about).pack(anchor="w", padx=18, pady=3)

        # Main row: spectrum and channels
        middle = tk.Frame(self.root, bg=BG)
        middle.pack(fill="both", expand=True, padx=17, pady=0)
        middle.grid_columnconfigure(0, weight=66)
        middle.grid_columnconfigure(1, weight=34)
        middle.grid_rowconfigure(0, weight=1)
        plot_card = Card(middle)
        table_card = Card(middle)
        plot_card.grid(row=0, column=0, sticky="nsew", padx=3)
        table_card.grid(row=0, column=1, sticky="nsew", padx=3)
        label(plot_card.body, "Espectro da Fonte Luminosa", 13, "bold",
              PURPLE_DARK).pack(anchor="w", pady=(2, 0))
        self.figure = Figure(figsize=(8.5, 5), dpi=96, facecolor=CARD)
        self.ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.09, right=0.97, top=0.94, bottom=0.23)
        self.chart = FigureCanvasTkAgg(self.figure, master=plot_card.body)
        self.chart.get_tk_widget().pack(fill="both", expand=True)

        label(table_card.body, "Dados dos 8 canais", 13, "bold",
              PURPLE_DARK).pack(anchor="w", pady=(2, 7))
        headings = tk.Frame(table_card.body, bg=LILAC)
        headings.pack(fill="x", pady=(0, 3))
        for i, text in enumerate(("Canal", "λ (nm)", "Valor bruto", "Normalizado")):
            headings.grid_columnconfigure(i, weight=1, uniform="columns")
            label(headings, text, 9, "bold", INK, LILAC).grid(row=0, column=i,
                                                                sticky="nsew", pady=8)
        self.cells = []
        for i in range(8):
            stripe = CARD if i % 2 == 0 else "#FAF7FF"
            row = tk.Frame(table_card.body, bg=stripe, height=27)
            row.pack(fill="x", pady=1)
            for col in range(4):
                row.grid_columnconfigure(col, weight=1, uniform="columns")
            c0 = label(row, CHANNELS[i], 10, "bold", "white" if i not in (4, 5) else INK,
                       COLORS[i]); c0.grid(row=0, column=0, sticky="nsew")
            c1 = label(row, str(int(WAVELENGTHS[i])), 10, color=INK, bg=stripe)
            c1.grid(row=0, column=1, sticky="nsew")
            c2 = label(row, "—", 10, "bold", INK, stripe)
            c2.grid(row=0, column=2, sticky="nsew")
            c3 = label(row, "—", 10, color=INK, bg=stripe)
            c3.grid(row=0, column=3, sticky="nsew")
            self.cells.append((c2, c3))
        self.peak_box = tk.Frame(table_card.body, bg="#FFF1E9", padx=12, pady=12)
        self.peak_box.pack(fill="x", pady=(10, 0))
        label(self.peak_box, "Pico predominante", 11, "bold", PURPLE_DARK,
              "#FFF1E9").pack(anchor="w")
        self.peak = label(self.peak_box, "Aguardando leitura", 18, "bold",
                          PURPLE_DARK, "#FFF1E9")
        self.peak.pack(anchor="w", pady=(3, 0))
        self.peak_info = label(table_card.body, "Os números são contagens do sensor, não lux.",
                               9, color=MUTED, wraplength=340, justify="left")
        self.peak_info.pack(anchor="w", pady=(7, 0))

        # Bottom row
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=17, pady=(6, 6))
        for i, w in enumerate((27, 39, 34)):
            bottom.grid_columnconfigure(i, weight=w, uniform="bottom")
        status_card, log_card, action_card = [Card(bottom, height=128) for _ in range(3)]
        for i, c in enumerate((status_card, log_card, action_card)):
            c.grid(row=0, column=i, sticky="nsew", padx=3)
        label(status_card.body, "Status", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(1, 8))
        self.status_panel = tk.Frame(status_card.body, bg=LILAC, padx=9, pady=10)
        self.status_panel.pack(fill="x")
        self.status_lbl = label(self.status_panel, "Aguardando conexão", 11, "bold", PURPLE_DARK,
                                LILAC, wraplength=260, justify="left")
        self.status_lbl.pack(anchor="w")
        # Os avisos detalhados permanecem no registro, sem sobrepor o status.
        label(log_card.body, "Registro de leituras", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(1, 4))
        self.log = tk.Text(log_card.body, height=4, font=("Consolas", 9),
                           relief="flat", wrap="word", bg="#FBF8FF", fg=INK, state="disabled")
        self.log.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        label(action_card.body, "Acoes", 12, "bold", PURPLE_DARK).pack(anchor="w", pady=(1, 8))
        ar = tk.Frame(action_card.body, bg=CARD)
        ar.pack(fill="x")
        RoundButton(ar, "Salvar PNG", self.save_png, bg="#EBD7FF", fg=PURPLE_DARK,
                    hover="#DBC0FA", width=143).pack(side="left", padx=(0, 6))
        RoundButton(ar, "Exportar CSV", self.export_csv, bg="#EBD7FF", fg=PURPLE_DARK,
                    hover="#DBC0FA", width=144).pack(side="left")

        # Footer, explicit educational credits and both email addresses
        footer = tk.Frame(self.root, bg="#E9D9FF", padx=20, pady=9)
        footer.pack(fill="x", side="bottom")
        label(footer, "Parte de um produto educacional", 10, "bold", PURPLE_DARK,
              "#E9D9FF").pack(side="left", padx=(0, 25))
        credit = tk.Frame(footer, bg="#E9D9FF")
        credit.pack(side="left", fill="x", expand=True)
        label(credit, "Desenvolvido por Aline Silva Santos Quinai", 10, "bold",
              PURPLE_DARK, "#E9D9FF").pack(anchor="w")
        label(credit, "Para aulas de Química e Astronomia, em conjunto com uma sequência didática.",
              9, color=INK, bg="#E9D9FF").pack(anchor="w")
        contact = tk.Frame(footer, bg="#E9D9FF")
        contact.pack(side="right", padx=(14, 0))
        label(contact, "Dúvidas? Entre em contato:", 9, "bold", PURPLE_DARK,
              "#E9D9FF").pack(anchor="w")
        label(contact, "alinequinai@unesp.br  |  santosaline248@gmail.com",
              9, color=INK, bg="#E9D9FF").pack(anchor="w")

        self.draw_chart(None)

    def log_message(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        if int(self.log.index("end-1c").split(".")[0]) > 80:
            self.log.delete("1.0", "15.0")
        self.log.configure(state="disabled")

    def set_status(self, text):
        self.status_var.set(text)
        self.status_lbl.configure(text=text)

    def detect_ports(self):
        ports = list(list_ports.comports())
        names = [p.device for p in ports]
        previous = self.port_var.get()
        self.portbox.configure(values=names)
        if previous in names:
            self.port_var.set(previous)
        elif ports:
            likely = next((p.device for p in ports if any(
                token in (p.description + ' ' + (p.manufacturer or '')).lower()
                for token in ('arduino', 'ch340', 'usb serial', 'cp210'))), names[0])
            self.port_var.set(likely)
        else:
            self.port_var.set("")
        self.log_message("Portas detectadas: " + (", ".join(names) if names else "nenhuma"))

    def post(self, kind, payload=None):
        try:
            self.events.put_nowait((kind, payload))
        except queue.Full:
            # Descarta leitura antiga em vez de bloquear a serial.
            try:
                self.events.get_nowait()
                self.events.put_nowait((kind, payload))
            except queue.Empty:
                pass

    def start(self):
        if self.running:
            return
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("Porta COM", "Conecte o Arduino e selecione a porta COM.")
            return
        self.stop_event.clear()
        self.running = True
        self.calibration_done = False
        self.dark = np.zeros(8)
        self.last_raw = None
        self.last_corr = None
        self.last_norm = None
        self.start_btn.enable(False)
        self.stop_btn.enable(True)
        self.set_status("Calibrando: tampe completamente o sensor")
        self.log_message("Abrindo " + port + ". Mantenha o sensor tampado.")
        self.thread = threading.Thread(target=self.worker, args=(port, self.stop_event), daemon=True)
        self.thread.start()

    def worker(self, port, stop):
        ser = None
        try:
            ser = serial.Serial(port, BAUD, timeout=1.2)
            self.serial_port = ser
            # A abertura da porta reinicia algumas placas Arduino.
            if stop.wait(3.0):
                return
            ser.reset_input_buffer()
            samples = []
            last_valid = time.monotonic()
            self.post("log", "Calibracao iniciada: aguardando 20 leituras validas. Clique em Parar para cancelar.")
            # O AS7341 pode levar varios segundos por leitura com ganho/tempo
            # de integracao elevados. Nao transformar leituras lentas em uma
            # calibracao parcial: a media so e calculada apos 20 amostras.
            while not stop.is_set() and len(samples) < DARK_SAMPLES:
                text = ser.readline().decode(errors="ignore")
                raw = parse_csv(text)
                if raw is not None:
                    samples.append(raw)
                    last_valid = time.monotonic()
                    self.post("progress", len(samples))
                elif time.monotonic() - last_valid > 15:
                    self.post("waiting", len(samples))
                    last_valid = time.monotonic()
            if stop.is_set():
                return
            dark = np.mean(samples, axis=0)
            self.post("calibrated", dark)
            while not stop.is_set():
                raw = parse_csv(ser.readline().decode(errors="ignore"))
                if raw is not None:
                    self.post("reading", raw)
        except (serial.SerialException, OSError, ValueError) as exc:
            if not stop.is_set():
                self.post("error", f"Falha na comunicação serial: {exc}")
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            self.serial_port = None
            self.post("done")

    def stop(self):
        if self.running:
            self.set_status("Encerrando a comunicação...")
            self.stop_event.set()
            self.stop_btn.enable(False)

    def consume_events(self):
        latest = None
        for _ in range(80):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.set_status(f"Calibrando o fundo: {data}/{DARK_SAMPLES} leituras")
                self.log_message(f"Calibracao: {data}/{DARK_SAMPLES}")
            elif kind == "calibrated":
                self.dark = data
                self.calibration_done = True
                self.set_status("Calibração concluída. Exponha o sensor à luz.")
                self.log_message("Calibração concluída; medição iniciada.")
            elif kind == "reading":
                latest = data
            elif kind == "log":
                self.log_message(data)
            elif kind == "waiting":
                self.set_status(f"Aguardando sensor: {data}/{DARK_SAMPLES} leituras")
                self.log_message("Sem nova leitura valida nos ultimos 15 s. Verifique a COM e o sensor; clique em Parar para cancelar.")
            elif kind == "error":
                self.set_status("Erro de comunicacao")
                self.log_message(data)
                messagebox.showerror("Espectrometro AS7341", data)
            elif kind == "done":
                self.running = False
                self.start_btn.enable(True)
                self.stop_btn.enable(False)
                if self.stop_event.is_set():
                    self.set_status("Experimento encerrado")
                    self.log_message("Experimento encerrado.")
                elif not self.calibration_done:
                    self.set_status("Conexão encerrada — verifique o Arduino")
        if latest is not None and self.calibration_done:
            self.last_raw = latest.copy()
            # Evita saturar a interface com desenhos acumulados.
            now = time.monotonic()
            if now - self.last_update > 0.16:
                self.redraw()
                self.last_update = now
        self.root.after(100, self.consume_events)

    def redraw(self):
        if self.last_raw is None:
            self.draw_chart(None)
            return
        corrected, normalized, vmax = processed_reading(
            self.last_raw, self.dark, self.correction.get())
        self.last_corr = corrected
        self.last_norm = normalized
        for i, (raw_label, normalized_label) in enumerate(self.cells):
            raw_label.configure(text=str(int(self.last_raw[i])))
            normalized_label.configure(text=f"{normalized[i]:.2f}".replace(".", ",") if vmax >= MIN_SIGNAL else "—")
        if vmax >= MIN_SIGNAL:
            idx = int(np.argmax(normalized))
            self.peak.configure(text=f"{int(WAVELENGTHS[idx])} nm ({CHANNELS[idx]})")
            self.peak_info.configure(text=f"{NAMES[idx].capitalize()} · leitura bruta: {int(self.last_raw[idx])}")
        else:
            self.peak.configure(text="Sinal insuficiente")
            self.peak_info.configure(text="Valores mostrados na tabela; sem pico confiável.")
        self.draw_chart(normalized if vmax >= MIN_SIGNAL else np.zeros(8))

    def draw_chart(self, y):
        ax = self.ax
        ax.clear()
        bg = LinearSegmentedColormap.from_list("visible", [
            "#8D47D8", "#3654E8", "#32C5ED", "#38D77B", "#E3FF5A", "#FFCA48", "#FB454D", "#C91D53"])
        gradient = np.linspace(0, 1, 600)[None, :]
        ax.imshow(gradient, extent=[405, 690, 0, 1.15], cmap=bg, origin="lower",
                  aspect="auto", alpha=0.32, zorder=0)
        mode = self.graph_type.get()
        ax.set_facecolor("#FFFFFF")
        ax.set_xlim(405, 690)
        ax.set_ylim(0, 1.18)
        ax.set_xticks(WAVELENGTHS)
        ax.set_xticklabels([f"{int(w)}\n({ch})" for w, ch in zip(WAVELENGTHS, CHANNELS)], fontsize=9)
        ax.set_yticks(np.linspace(0, 1, 6))
        ax.grid(axis="y", alpha=0.18, zorder=1)
        ax.set_xlabel("Comprimento de onda (nm)", fontsize=10, color=INK)
        ax.set_ylabel("Intensidade normalizada", fontsize=10, color=INK)
        for spine in ax.spines.values():
            spine.set_color("#CFBCEC")
        if y is None:
            ax.text(547, 0.60, "Conecte o Arduino e clique em Iniciar Experimento",
                    ha="center", va="center", color=PURPLE_DARK, fontsize=12,
                    bbox=dict(boxstyle="round,pad=0.6", facecolor="white", edgecolor=BORDER))
        else:
            if mode in ("Apenas Barras", "Barras + Curva"):
                bars = ax.bar(WAVELENGTHS, y, color=COLORS, width=17, edgecolor=INK,
                              linewidth=0.7, zorder=3, alpha=0.92)
                if self.last_raw is not None:
                    for bar, value in zip(bars, self.last_raw):
                        ax.text(bar.get_x() + bar.get_width()/2,
                                min(1.13, bar.get_height() + 0.025), str(int(value)),
                                ha="center", va="bottom", fontsize=9, fontweight="bold", color=INK, zorder=6)
            if mode in ("Apenas Curva", "Barras + Curva"):
                xs = np.linspace(415, 680, 450)
                # PCHIP evita picos artificiais entre os oito valores lidos.
                ys = np.clip(PchipInterpolator(WAVELENGTHS, y)(xs), 0, 1.0)
                ax.plot(xs, ys, color="#26102F", linewidth=2.7, zorder=4)
                ax.scatter(WAVELENGTHS, y, s=32, color="white", edgecolor="#26102F", zorder=5)
        self.chart.draw_idle()

    def save_png(self):
        if self.last_raw is None:
            messagebox.showinfo("Sem dados", "Realize uma medição antes de salvar o gráfico.")
            return
        path = filedialog.asksaveasfilename(title="Salvar gráfico", defaultextension=".png",
                                            filetypes=[("Imagem PNG", "*.png")],
                                            initialfile="espectro_AS7341.png")
        if path:
            try:
                self.figure.savefig(path, dpi=300, bbox_inches="tight")
                self.log_message("Gráfico salvo: " + path)
            except Exception as exc:
                messagebox.showerror("Falha ao salvar", str(exc))

    def export_csv(self):
        if self.last_raw is None:
            messagebox.showinfo("Sem dados", "Realize uma medição antes de exportar.")
            return
        path = filedialog.asksaveasfilename(title="Exportar dados", defaultextension=".csv",
                                            filetypes=[("Arquivo CSV", "*.csv")],
                                            initialfile="dados_AS7341.csv")
        if path:
            try:
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(["Espectrômetro didático AS7341", datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
                    writer.writerow(["Correção espectral didática", "Ativada" if self.correction.get() else "Desativada"])
                    writer.writerow(["Canal", "Comprimento de onda (nm)", "Bruto (contagens)",
                                     "Fundo médio", "Após tratamento", "Intensidade normalizada"])
                    for i in range(8):
                        writer.writerow([CHANNELS[i], int(WAVELENGTHS[i]), int(self.last_raw[i]),
                                         round(float(self.dark[i]), 3), round(float(self.last_corr[i]), 3),
                                         round(float(self.last_norm[i]), 6)])
                self.log_message("CSV exportado: " + path)
            except Exception as exc:
                messagebox.showerror("Falha ao exportar", str(exc))

    def show_about(self):
        modal = tk.Toplevel(self.root)
        modal.title("Sobre • Espectrômetro didático AS7341")
        modal.geometry("810x690")
        modal.minsize(630, 500)
        modal.configure(bg=BG)
        modal.transient(self.root)
        modal.grab_set()
        label(modal, "Sobre o aplicativo", 23, "bold", PURPLE_DARK, BG).pack(anchor="w", padx=30, pady=(22, 10))
        outer = tk.Frame(modal, bg=BG)
        outer.pack(fill="both", expand=True, padx=29, pady=(0, 8))
        scroll = tk.Scrollbar(outer)
        scroll.pack(side="right", fill="y")
        text = tk.Text(outer, wrap="word", font=(FONT, 11), bg=CARD, fg=INK,
                       padx=23, pady=20, relief="flat", yscrollcommand=scroll.set)
        text.pack(fill="both", expand=True)
        scroll.config(command=text.yview)
        sections = [
            ("O que este aplicativo faz?", "Recebe as leituras de oito canais espectrais do sensor AS7341 conectado a um Arduino e as apresenta em barras, curva interpolada ou nas duas representações. Os números das barras são as contagens brutas enviadas pela placa; não são lux ou potência absoluta."),
            ("O que é a calibração do sinal de escuro?", "Ao clicar em Iniciar, mantenha o sensor completamente tampado. O programa recolhe 20 leituras e calcula a média de cada canal sem iluminação. Essa média é subtraída das leituras seguintes para reduzir o fundo eletrônico. O sinal negativo é limitado a zero. A calibração de escuro NÃO corrige a sensibilidade espectral desigual dos canais. Se a iluminação, o ganho ou a integração do Arduino forem alterados, refaça a calibração."),
            ("O que é a correção espectral?", "É uma ponderação matemática dos canais para tentar compensar diferenças na resposta do instrumento. A opção desta versão utiliza apenas fatores exploratórios: NÃO foi determinada por uma fonte padrão rastreável e NÃO representa calibração radiométrica. Por isso, fica desativada por padrão e não deve ser usada para afirmar que o espectro obtido é o espectro físico absoluto da fonte."),
            ("Qual é a diferença entre barras e curva?", "As barras correspondem diretamente às oito bandas medidas. A curva é uma interpolação matemática entre esses pontos e não mede a emissão nas posições intermediárias. Nesta versão, a interpolação PCHIP evita criar máximos e mínimos entre medições, mas ainda não permite identificar linhas estreitas ou regiões sem emissão que o sensor não resolve."),
            ("Como interpretar o pico predominante?", "É o canal que apresenta a maior contagem após a correção do escuro e eventual ponderação. Seu comprimento de onda é aproximado e representa uma banda, não uma linha espectral determinada com exatidão. A resposta desigual dos filtros deve ser considerada ao comparar cores ou fontes."),
            ("Produto educacional e autoria", "Este aplicativo integra um produto educacional desenvolvido por Aline Silva Santos Quinai para utilização em aulas de Química e Astronomia, em conjunto com uma sequência didática. Em caso de dúvidas, entre em contato: alinequinai@unesp.br ou santosaline248@gmail.com."),
        ]
        text.tag_configure("heading", font=(FONT, 12, "bold"), foreground=PURPLE_DARK, spacing1=13, spacing3=6)
        for title, body in sections:
            text.insert("end", title + "\n", "heading")
            text.insert("end", body + "\n\n")
        text.configure(state="disabled")
        RoundButton(modal, "Fechar", modal.destroy, width=110).pack(anchor="e", padx=30, pady=(2, 14))

    def on_close(self):
        self.stop_event.set()
        # A leitura é em thread daemon e a porta será fechada no finally.
        self.root.destroy()


def main():
    root = tk.Tk()
    icon_file = resource_path("atom_purple.ico")
    try:
        if Path(icon_file).exists():
            root.iconbitmap(icon_file)
    except Exception:
        pass
    EspectrometroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

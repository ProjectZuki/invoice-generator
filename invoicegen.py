"""
Invoice Generator
A desktop application for generating professional PDF invoices.

It provides a themed (dark/light) Tkinter GUI for entering company details,
customer information and line items, previews running totals live, supports
saving/loading drafts, tracks invoice numbers in SQLite, and renders an A4
PDF invoice with ReportLab.

Attributes:
    company_name, address, city_st_zip, phone_no, email (tk.StringVar):
        The issuing company's contact details.
    customer_name, customer_email, customer_address, customer_city (tk.StringVar):
        The recipient's contact details.
    date, due_date (tk.StringVar): Invoice and payment-due dates.
    authorized_signatory (tk.StringVar): Name signing the invoice.
    line_items (list[dict]): Line items, each with date/description/location/rate vars.
"""

# import required libraries
import os
import re
import json
import sqlite3
import datetime
from datetime import timedelta
import textwrap
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox

from tkcalendar import Calendar
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color

try:  # Pillow is optional; only used for the in-app logo preview.
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - graceful fallback
    _PIL_AVAILABLE = False


CONFIG_KEYS = {
    "companyimage_file_name",
    "signature_file_name",
    "company_name",
    "address",
    "city_st_zip",
    "phone_no",
    "email",
    "customer_name",
    "customer_email",
    "customer_address",
    "customer_city",
}

INVOICE_COUNTER_DB = "invoice_counter.db"
INVOICE_COUNTER_KEY = "last_invoice_number"
THEME_MODE_KEY = "theme_mode"
LEGACY_INVOICE_NUMBER_FILE = "invoice_number.txt"
DRAFTS_TABLE = "invoice_drafts"

DEFAULT_NOTE = "Your business is greatly appreciated."

# regex used to keep money entries clean (digits with up to two decimals)
_MONEY_RE = re.compile(r"^\d*\.?\d{0,2}$")


# colour palettes for the two themes
THEMES = {
    "dark": {
        "bg": "#14161c",
        "panel_bg": "#1e212b",
        "fg": "#e7ebf3",
        "muted_fg": "#9aa4b8",
        "entry_bg": "#272b37",
        "entry_fg": "#f2f5fb",
        "button_bg": "#2c313f",
        "button_fg": "#e7ebf3",
        "accent_bg": "#4c8dff",
        "accent_fg": "#0b1020",
        "accent_active_bg": "#6ba0ff",
        "danger_bg": "#d9534f",
        "danger_active_bg": "#e46b67",
        "success_fg": "#3ecf8e",
        "border": "#353b4d",
    },
    "light": {
        "bg": "#eef1f6",
        "panel_bg": "#ffffff",
        "fg": "#1d2433",
        "muted_fg": "#5b6478",
        "entry_bg": "#ffffff",
        "entry_fg": "#111827",
        "button_bg": "#e4e9f2",
        "button_fg": "#1d2433",
        "accent_bg": "#2563eb",
        "accent_fg": "#ffffff",
        "accent_active_bg": "#3b76ee",
        "danger_bg": "#dc2626",
        "danger_active_bg": "#e4453f",
        "success_fg": "#16a34a",
        "border": "#cdd5e3",
    },
}


class InvoiceGeneratorApp(tk.Tk):
    def __init__(self):
        """Initialize the application window, state and widgets."""
        super().__init__()
        self.title("Invoice Generator")
        self.minsize(840, 640)

        # ---- defaults (set before config load to avoid missing attributes) ----
        self.companyimage_file_name = ""
        self.signature_file_name = ""
        self.company_name = tk.StringVar(value="")
        self.address = tk.StringVar(value="")
        self.city_st_zip = tk.StringVar(value="")
        self.phone_no = tk.StringVar(value="")
        self.email = tk.StringVar(value="")
        self.customer_name = tk.StringVar(value="")
        self.customer_email = tk.StringVar(value="")
        self.customer_address = tk.StringVar(value="")
        self.customer_city = tk.StringVar(value="")

        # initialize values from config file
        self.load_config("config.txt")

        # dates
        today = datetime.date.today()
        self.date = tk.StringVar(value=today.strftime("%d %B %Y"))
        self.due_date = tk.StringVar(value=(today + timedelta(days=15)).strftime("%d %B %Y"))

        # signatory is its own variable (defaults to the company name)
        self.authorized_signatory = tk.StringVar(value=self.company_name.get())
        self.invoice_number_var = tk.StringVar(value="")
        self.total_var = tk.StringVar(value="$0.00")
        self.subtotal_var = tk.StringVar(value="0 line items")
        self.status_var = tk.StringVar(value="Ready.")
        self.theme_toggle_var = tk.StringVar(value="")

        # line item + window state
        self.line_items = []  # list of dicts: {date, description, location, rate}
        self.line_items_container = None
        self.drafts_manager_window = None
        self.date_window = None
        self._logo_image = None  # keep a reference so the preview isn't GC'd

        # persistent storage + theme
        self.initialize_invoice_counter()
        self.initialize_drafts_storage()
        self.theme_mode = self.get_saved_theme_mode()
        self.theme = THEMES[self.theme_mode]

        # styling + widgets
        self.style = ttk.Style(self)
        self._configure_styles()
        self.configure(bg=self.theme["bg"])
        self.create_widgets()
        self.refresh_invoice_number_field()
        self.recompute_totals()
        self._center_window(960, 880)

    # ------------------------------------------------------------------ config
    def load_config(self, file_path):
        """Load configuration from a file and set default field values."""
        if not os.path.isfile(file_path):
            messagebox.showerror("Error", f"Configuration file not found: {file_path}")
            return

        setters = {
            "company_name": self.company_name,
            "address": self.address,
            "city_st_zip": self.city_st_zip,
            "phone_no": self.phone_no,
            "email": self.email,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "customer_address": self.customer_address,
            "customer_city": self.customer_city,
        }

        with open(file_path, "r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    messagebox.showwarning(
                        "Config Warning",
                        f"Skipping invalid config line {line_number}: {line}",
                    )
                    continue

                key, value = (part.strip() for part in line.split("=", 1))
                if key not in CONFIG_KEYS:
                    continue

                if key == "companyimage_file_name":
                    self.companyimage_file_name = value
                elif key == "signature_file_name":
                    self.signature_file_name = value
                elif key in setters:
                    setters[key].set(value)

    # ------------------------------------------------------------------ styling
    def _configure_styles(self):
        """(Re)configure ttk styles for the active theme."""
        t = self.theme
        s = self.style
        s.theme_use("clam")

        base_font = ("Segoe UI", 10)
        s.configure(".", background=t["bg"], foreground=t["fg"], font=base_font)

        # frames / labels
        s.configure("TFrame", background=t["bg"])
        s.configure("Card.TFrame", background=t["panel_bg"])
        s.configure("Header.TFrame", background=t["panel_bg"])
        s.configure("Footer.TFrame", background=t["panel_bg"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"], font=base_font)
        s.configure("Card.TLabel", background=t["panel_bg"], foreground=t["fg"])
        s.configure("CardMuted.TLabel", background=t["panel_bg"], foreground=t["muted_fg"],
                    font=("Segoe UI", 9))
        s.configure("Header.TLabel", background=t["panel_bg"], foreground=t["fg"])
        s.configure("Title.TLabel", background=t["panel_bg"], foreground=t["fg"],
                    font=("Segoe UI Semibold", 20))
        s.configure("Badge.TLabel", background=t["panel_bg"], foreground=t["accent_bg"],
                    font=("Segoe UI Semibold", 11))
        s.configure("Status.TLabel", background=t["panel_bg"], foreground=t["muted_fg"],
                    font=("Segoe UI", 9))
        s.configure("Total.TLabel", background=t["panel_bg"], foreground=t["fg"],
                    font=("Segoe UI Semibold", 18))
        s.configure("TotalCaption.TLabel", background=t["panel_bg"], foreground=t["muted_fg"],
                    font=("Segoe UI", 9))

        # label frames (cards)
        s.configure("Card.TLabelframe", background=t["panel_bg"],
                    bordercolor=t["border"], relief="solid", borderwidth=1)
        s.configure("Card.TLabelframe.Label", background=t["panel_bg"],
                    foreground=t["accent_bg"], font=("Segoe UI Semibold", 12))

        # entries
        s.configure("TEntry", fieldbackground=t["entry_bg"], foreground=t["entry_fg"],
                    insertcolor=t["entry_fg"], bordercolor=t["border"],
                    lightcolor=t["border"], darkcolor=t["border"],
                    relief="flat", padding=6)
        s.map("TEntry", bordercolor=[("focus", t["accent_bg"])],
              lightcolor=[("focus", t["accent_bg"])])

        # buttons
        s.configure("TButton", background=t["button_bg"], foreground=t["button_fg"],
                    bordercolor=t["border"], focuscolor=t["accent_bg"],
                    relief="flat", padding=(14, 8), font=("Segoe UI", 10))
        s.map("TButton",
              background=[("active", t["accent_bg"]), ("pressed", t["accent_active_bg"])],
              foreground=[("active", t["accent_fg"])])

        s.configure("Accent.TButton", background=t["accent_bg"], foreground=t["accent_fg"],
                    font=("Segoe UI Semibold", 11), padding=(18, 10))
        s.map("Accent.TButton",
              background=[("active", t["accent_active_bg"]), ("pressed", t["accent_bg"])],
              foreground=[("active", t["accent_fg"])])

        s.configure("Danger.TButton", background=t["danger_bg"], foreground="#ffffff")
        s.map("Danger.TButton", background=[("active", t["danger_active_bg"])],
              foreground=[("active", "#ffffff")])

        s.configure("Ghost.TButton", background=t["panel_bg"], foreground=t["fg"],
                    padding=(10, 6))
        s.map("Ghost.TButton", background=[("active", t["button_bg"])],
              foreground=[("active", t["fg"])])

        s.configure("Icon.TButton", padding=(6, 2), font=("Segoe UI", 11),
                    background=t["panel_bg"], foreground=t["fg"])
        s.map("Icon.TButton", background=[("active", t["button_bg"])])

        s.configure("RowHead.TLabel", background=t["panel_bg"], foreground=t["muted_fg"],
                    font=("Segoe UI Semibold", 9))

        # treeview (drafts manager)
        s.configure("Treeview", background=t["panel_bg"], fieldbackground=t["panel_bg"],
                    foreground=t["fg"], bordercolor=t["border"], rowheight=28,
                    relief="flat")
        s.configure("Treeview.Heading", background=t["button_bg"], foreground=t["fg"],
                    relief="flat", font=("Segoe UI Semibold", 10))
        s.map("Treeview", background=[("selected", t["accent_bg"])],
              foreground=[("selected", t["accent_fg"])])

        # scrollbar
        s.configure("Vertical.TScrollbar", background=t["button_bg"], troughcolor=t["bg"],
                    bordercolor=t["bg"], arrowcolor=t["fg"])

    # ------------------------------------------------------------------ widgets
    def create_widgets(self):
        """Build the application's header, scrollable body and footer."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(20, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        title = ttk.Label(header, text="Invoice Generator", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        num_box = ttk.Frame(header, style="Header.TFrame")
        num_box.grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Label(num_box, text="Invoice #", style="Badge.TLabel").grid(
            row=0, column=0, padx=(0, 8))
        num_entry = ttk.Entry(num_box, textvariable=self.invoice_number_var, width=10)
        num_entry.grid(row=0, column=1)
        # a blank field snaps back to the next number when the user leaves it
        num_entry.bind("<FocusOut>", self._fill_invoice_number_if_blank)
        num_entry.bind("<Return>", self._fill_invoice_number_if_blank)
        ttk.Label(num_box, text="blank = next in sequence", style="Status.TLabel").grid(
            row=0, column=2, padx=(10, 0))

        theme_btn = ttk.Button(header, textvariable=self.theme_toggle_var,
                               command=self.toggle_theme, style="Icon.TButton", width=3)
        theme_btn.grid(row=0, column=2, sticky="e")
        self.refresh_theme_toggle_icon()

        # subtle divider beneath the header
        ttk.Separator(self, orient="horizontal").grid(row=0, column=0, sticky="sew")

    def _build_body(self):
        """Build a scrollable region containing all input cards."""
        outer = ttk.Frame(self)
        outer.grid(row=1, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        self.body_canvas = tk.Canvas(outer, highlightthickness=0, bg=self.theme["bg"])
        self.body_canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.body_canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.body_canvas.configure(yscrollcommand=scroll.set)

        body = ttk.Frame(self.body_canvas, padding=20)
        self._body_window = self.body_canvas.create_window((0, 0), window=body, anchor="nw")
        body.columnconfigure(0, weight=1, uniform="cards")
        body.columnconfigure(1, weight=1, uniform="cards")

        body.bind("<Configure>",
                  lambda e: self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all")))
        self.body_canvas.bind(
            "<Configure>",
            lambda e: self.body_canvas.itemconfigure(self._body_window, width=e.width))
        # mouse-wheel scrolling while the pointer is over the body
        self.body_canvas.bind(
            "<Enter>", lambda e: self.body_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.body_canvas.bind(
            "<Leave>", lambda e: self.body_canvas.unbind_all("<MouseWheel>"))

        self._build_company_card(body)
        self._build_customer_card(body)
        self._build_invoice_card(body)
        self._build_line_items_card(body)

    def _on_mousewheel(self, event):
        self.body_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _card(self, parent, title):
        card = ttk.LabelFrame(parent, text=f"  {title}  ", style="Card.TLabelframe",
                              padding=(16, 12))
        card.columnconfigure(1, weight=1)
        return card

    def _field(self, parent, label, variable, row, validate_money=False):
        """Add a labelled entry to a card grid, returning the entry widget."""
        ttk.Label(parent, text=label, style="Card.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 14), pady=6)
        entry = ttk.Entry(parent, textvariable=variable)
        if validate_money:
            vcmd = (self.register(self._validate_money), "%P")
            entry.configure(validate="key", validatecommand=vcmd)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        return entry

    @staticmethod
    def _validate_money(proposed):
        return proposed == "" or bool(_MONEY_RE.match(proposed))

    def _build_company_card(self, body):
        card = self._card(body, "Your Company")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 16))

        # optional logo preview
        self._logo_label = ttk.Label(card, style="Card.TLabel")
        self._logo_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._load_logo_preview()

        self._field(card, "Company Name", self.company_name, 1)
        self._field(card, "Address", self.address, 2)
        self._field(card, "City, State, ZIP", self.city_st_zip, 3)
        self._field(card, "Phone No", self.phone_no, 4)
        self._field(card, "Email", self.email, 5)

    def _build_customer_card(self, body):
        card = self._card(body, "Bill To (Customer)")
        card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 16))

        self._field(card, "Customer Name", self.customer_name, 0)
        self._field(card, "Email", self.customer_email, 1)
        self._field(card, "Address", self.customer_address, 2)
        self._field(card, "City, State, ZIP", self.customer_city, 3)
        ttk.Label(card, text="These details appear in the invoice's “Bill To” block.",
                  style="CardMuted.TLabel").grid(row=4, column=0, columnspan=2,
                                                 sticky="w", pady=(8, 0))

    def _build_invoice_card(self, body):
        card = self._card(body, "Invoice Details")
        card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

        # invoice date + due date side by side, each with a calendar picker
        ttk.Label(card, text="Invoice Date", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 14), pady=6)
        date_row = ttk.Frame(card, style="Card.TFrame")
        date_row.grid(row=0, column=1, sticky="ew", pady=6)
        date_row.columnconfigure(0, weight=1)
        ttk.Entry(date_row, textvariable=self.date).grid(row=0, column=0, sticky="ew")
        ttk.Button(date_row, text="📅", width=3, style="Icon.TButton",
                   command=lambda: self.select_date(self.date)).grid(row=0, column=1, padx=(6, 0))

        ttk.Label(card, text="Due Date", style="Card.TLabel").grid(
            row=0, column=2, sticky="w", padx=(20, 14), pady=6)
        due_row = ttk.Frame(card, style="Card.TFrame")
        due_row.grid(row=0, column=3, sticky="ew", pady=6)
        due_row.columnconfigure(0, weight=1)
        ttk.Entry(due_row, textvariable=self.due_date).grid(row=0, column=0, sticky="ew")
        ttk.Button(due_row, text="📅", width=3, style="Icon.TButton",
                   command=lambda: self.select_date(self.due_date)).grid(row=0, column=1, padx=(6, 0))

        self._field(card, "Authorized Signatory", self.authorized_signatory, 1)

    def _build_line_items_card(self, body):
        card = self._card(body, "Line Items")
        card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        card.columnconfigure(0, weight=1)

        self.line_items_container = ttk.Frame(card, style="Card.TFrame")
        self.line_items_container.grid(row=0, column=0, sticky="ew")
        self.line_items_container.columnconfigure(2, weight=1)  # description expands

        add_btn = ttk.Button(card, text="＋  Add Line", style="Ghost.TButton",
                             command=self.add_line_item_row)
        add_btn.grid(row=1, column=0, sticky="w", pady=(12, 0))

        if not self.line_items:
            self._new_line_item()  # start with one empty row
        self._rebuild_line_items()

    def _build_footer(self):
        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, sticky="new")
        footer = ttk.Frame(self, style="Footer.TFrame", padding=(20, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)

        totals = ttk.Frame(footer, style="Footer.TFrame")
        totals.grid(row=0, column=0, sticky="w")
        ttk.Label(totals, textvariable=self.subtotal_var, style="TotalCaption.TLabel").grid(
            row=0, column=0, sticky="w")
        total_box = ttk.Frame(totals, style="Footer.TFrame")
        total_box.grid(row=1, column=0, sticky="w")
        ttk.Label(total_box, text="Total", style="TotalCaption.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(total_box, textvariable=self.total_var, style="Total.TLabel").grid(
            row=0, column=1, sticky="w")

        actions = ttk.Frame(footer, style="Footer.TFrame")
        actions.grid(row=0, column=2, sticky="e")
        ttk.Button(actions, text="Save Draft", style="Ghost.TButton",
                   command=self.prompt_save_draft).grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Manage Drafts", style="Ghost.TButton",
                   command=self.open_drafts_manager).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Generate Invoice", style="Accent.TButton",
                   command=self.generate_invoice).grid(row=0, column=2, padx=(4, 0))

        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _load_logo_preview(self):
        """Show a small logo thumbnail in the company card when possible."""
        self._logo_image = None
        self._logo_label.configure(image="", text="")
        if not (_PIL_AVAILABLE and self.companyimage_file_name
                and os.path.isfile(self.companyimage_file_name)):
            self._logo_label.grid_remove()
            return
        try:
            img = Image.open(self.companyimage_file_name)
            img.thumbnail((160, 64))
            self._logo_image = ImageTk.PhotoImage(img)
            self._logo_label.configure(image=self._logo_image)
            self._logo_label.grid()
        except Exception:
            self._logo_label.grid_remove()

    # ------------------------------------------------------------- line items
    def _new_line_item(self, date="", description="", location="", rate=""):
        item = {
            "date": tk.StringVar(value=date),
            "description": tk.StringVar(value=description),
            "location": tk.StringVar(value=location),
            "rate": tk.StringVar(value=rate),
        }
        item["rate"].trace_add("write", lambda *_: self.recompute_totals())
        self.line_items.append(item)
        return item

    def add_line_item_row(self):
        """Add a new empty line-item row and refresh the table."""
        self._new_line_item()
        self._rebuild_line_items()
        self.recompute_totals()

    def remove_line_item_row(self, item):
        """Remove a line-item row (always leaving at least one)."""
        if item in self.line_items:
            self.line_items.remove(item)
        if not self.line_items:
            self._new_line_item()
        self._rebuild_line_items()
        self.recompute_totals()

    def _rebuild_line_items(self):
        """Render all line-item rows from current state."""
        if self.line_items_container is None or not self.line_items_container.winfo_exists():
            return
        for child in self.line_items_container.winfo_children():
            child.destroy()

        headers = [("Date", 0), ("", 1), ("Description", 2), ("Location", 3),
                   ("Rate ($)", 4), ("", 5)]
        for text, col in headers:
            if text:
                ttk.Label(self.line_items_container, text=text, style="RowHead.TLabel").grid(
                    row=0, column=col, sticky="w", padx=4, pady=(0, 4))

        for i, item in enumerate(self.line_items, start=1):
            ttk.Entry(self.line_items_container, textvariable=item["date"], width=12).grid(
                row=i, column=0, padx=4, pady=3, sticky="w")
            ttk.Button(self.line_items_container, text="📅", width=3, style="Icon.TButton",
                       command=lambda v=item["date"]: self.select_date(v)).grid(
                row=i, column=1, padx=(0, 4), pady=3)
            ttk.Entry(self.line_items_container, textvariable=item["description"]).grid(
                row=i, column=2, padx=4, pady=3, sticky="ew")
            ttk.Entry(self.line_items_container, textvariable=item["location"], width=18).grid(
                row=i, column=3, padx=4, pady=3, sticky="w")
            vcmd = (self.register(self._validate_money), "%P")
            ttk.Entry(self.line_items_container, textvariable=item["rate"], width=10,
                      validate="key", validatecommand=vcmd).grid(
                row=i, column=4, padx=4, pady=3, sticky="w")
            ttk.Button(self.line_items_container, text="✕", width=3, style="Icon.TButton",
                       command=lambda it=item: self.remove_line_item_row(it)).grid(
                row=i, column=5, padx=(0, 4), pady=3)

    def recompute_totals(self):
        """Recalculate the live subtotal/total shown in the footer."""
        subtotal = 0.0
        counted = 0
        for item in self.line_items:
            raw = item["rate"].get().strip()
            if not raw:
                continue
            try:
                subtotal += float(raw)
                counted += 1
            except ValueError:
                continue

        self.subtotal_var.set(f"{counted} line item{'' if counted == 1 else 's'}")
        self.total_var.set(self._money(subtotal))
        return subtotal

    @staticmethod
    def _money(value):
        return f"${value:,.2f}"

    # ------------------------------------------------------------------- dates
    def select_date(self, target_date_var):
        """Open a themed calendar popup that sets target_date_var."""
        top = tk.Toplevel(self)
        self.date_window = top
        top.title("Select Date")
        top.configure(bg=self.theme["bg"])
        top.transient(self)
        top.resizable(False, False)

        def on_close():
            self.date_window = None
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_close)

        today = datetime.date.today()
        cal = Calendar(
            top, selectmode="day", year=today.year, month=today.month, day=today.day,
            background=self.theme["panel_bg"], foreground=self.theme["fg"],
            headersbackground=self.theme["entry_bg"], headersforeground=self.theme["fg"],
            normalbackground=self.theme["panel_bg"], normalforeground=self.theme["fg"],
            weekendbackground=self.theme["entry_bg"], weekendforeground=self.theme["fg"],
            selectbackground=self.theme["accent_bg"], selectforeground=self.theme["accent_fg"],
            bordercolor=self.theme["border"],
        )
        cal.pack(padx=20, pady=20)

        def set_date():
            date_str = cal.get_date()
            parsed = datetime.datetime.strptime(date_str, "%m/%d/%y")
            target_date_var.set(parsed.strftime("%d %B %Y"))
            on_close()

        ttk.Button(top, text="Set Date", style="Accent.TButton", command=set_date).pack(
            pady=(0, 20))
        self._center_window_over(top)

    # ------------------------------------------------------------------ drafts
    def initialize_drafts_storage(self):
        """Initialize SQLite storage for invoice drafts."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {DRAFTS_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to initialize drafts storage: {exc}")

    def prompt_save_draft(self):
        """Prompt for a draft name and save the current invoice state."""
        draft_name = self._ask_string("Save Draft", "Enter a name for this draft:")
        if draft_name is None:
            return
        draft_name = draft_name.strip()
        if not draft_name:
            messagebox.showerror("Error", "Draft name cannot be empty.")
            return
        self.save_draft(draft_name)

    def save_draft(self, draft_name):
        """Save the current form and line items to drafts storage."""
        payload = {
            "company_name": self.company_name.get().strip(),
            "address": self.address.get().strip(),
            "city_st_zip": self.city_st_zip.get().strip(),
            "phone_no": self.phone_no.get().strip(),
            "email": self.email.get().strip(),
            "customer_name": self.customer_name.get().strip(),
            "customer_email": self.customer_email.get().strip(),
            "customer_address": self.customer_address.get().strip(),
            "customer_city": self.customer_city.get().strip(),
            "date": self.date.get().strip(),
            "due_date": self.due_date.get().strip(),
            "authorized_signatory": self.authorized_signatory.get().strip(),
            "line_items": [
                {
                    "date": item["date"].get().strip(),
                    "description": item["description"].get().strip(),
                    "location": item["location"].get().strip(),
                    "rate": item["rate"].get().strip(),
                }
                for item in self.line_items
            ],
        }
        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                conn.execute(
                    f"""
                    INSERT INTO {DRAFTS_TABLE} (name, payload, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        payload = excluded.payload,
                        updated_at = excluded.updated_at
                    """,
                    (draft_name, json.dumps(payload), now_iso),
                )
                conn.commit()
            self.set_status(f"Draft '{draft_name}' saved.")
            messagebox.showinfo("Success", f"Draft '{draft_name}' saved.")
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to save draft: {exc}")

    def open_drafts_manager(self):
        """Open the drafts manager window (load / delete saved drafts)."""
        if self.drafts_manager_window is not None and self.drafts_manager_window.winfo_exists():
            self.drafts_manager_window.lift()
            self.drafts_manager_window.focus_force()
            return

        manager = tk.Toplevel(self)
        self.drafts_manager_window = manager
        manager.title("Drafts")
        manager.geometry("560x420")
        manager.configure(bg=self.theme["bg"])
        manager.transient(self)

        def on_close():
            self.drafts_manager_window = None
            manager.destroy()

        manager.protocol("WM_DELETE_WINDOW", on_close)

        container = ttk.Frame(manager, padding=16)
        container.pack(fill="both", expand=True)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        ttk.Label(container, text="Saved Drafts", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10))

        tree = ttk.Treeview(container, columns=("name", "updated"), show="headings",
                            selectmode="browse")
        tree.heading("name", text="Name")
        tree.heading("updated", text="Last Updated")
        tree.column("name", width=240)
        tree.column("updated", width=200)
        tree.grid(row=1, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree_scroll.grid(row=1, column=1, sticky="ns")
        tree.configure(yscrollcommand=tree_scroll.set)

        def refresh():
            tree.delete(*tree.get_children())
            for name, updated_at in self.get_saved_drafts():
                tree.insert("", "end", iid=name, values=(name, updated_at))

        def selected_name():
            sel = tree.selection()
            return sel[0] if sel else None

        def load_selected():
            name = selected_name()
            if not name:
                messagebox.showerror("Error", "Select a draft to load.")
                return
            if self.load_draft(name):
                self.set_status(f"Draft '{name}' loaded.")
                on_close()

        def delete_selected():
            name = selected_name()
            if not name:
                messagebox.showerror("Error", "Select a draft to delete.")
                return
            if messagebox.askyesno("Confirm Delete", f"Delete draft '{name}'?"):
                if self.delete_draft(name):
                    refresh()

        tree.bind("<Double-1>", lambda e: load_selected())

        buttons = ttk.Frame(container)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Load", style="Accent.TButton",
                   command=load_selected).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Refresh", style="Ghost.TButton",
                   command=refresh).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Delete", style="Danger.TButton",
                   command=delete_selected).grid(row=0, column=2, padx=4)

        refresh()
        self._center_window_over(manager)

    def get_saved_drafts(self):
        """Return [(name, updated_at), ...] ordered by most recent."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                return conn.execute(
                    f"SELECT name, updated_at FROM {DRAFTS_TABLE} ORDER BY updated_at DESC"
                ).fetchall()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to fetch drafts: {exc}")
            return []

    def load_draft(self, draft_name):
        """Load a draft's values into the current form."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                row = conn.execute(
                    f"SELECT payload FROM {DRAFTS_TABLE} WHERE name = ?", (draft_name,)
                ).fetchone()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to load draft: {exc}")
            return False

        if not row:
            messagebox.showerror("Error", f"Draft '{draft_name}' not found.")
            return False

        try:
            payload = json.loads(row[0])
        except (TypeError, ValueError):
            messagebox.showerror("Error", "Draft payload is invalid.")
            return False

        self.company_name.set(payload.get("company_name", ""))
        self.address.set(payload.get("address", ""))
        self.city_st_zip.set(payload.get("city_st_zip", ""))
        self.phone_no.set(payload.get("phone_no", ""))
        self.email.set(payload.get("email", ""))
        self.customer_name.set(payload.get("customer_name", ""))
        self.customer_email.set(payload.get("customer_email", ""))
        self.customer_address.set(payload.get("customer_address", ""))
        self.customer_city.set(payload.get("customer_city", ""))
        self.date.set(payload.get("date", ""))
        self.due_date.set(payload.get("due_date", self.due_date.get()))
        self.authorized_signatory.set(payload.get("authorized_signatory", ""))

        self.line_items = []
        for item in payload.get("line_items", []):
            self._new_line_item(item.get("date", ""), item.get("description", ""),
                                item.get("location", ""), item.get("rate", ""))
        if not self.line_items:
            self._new_line_item()

        self._rebuild_line_items()
        self.recompute_totals()
        return True

    def delete_draft(self, draft_name):
        """Delete a draft by name."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                result = conn.execute(
                    f"DELETE FROM {DRAFTS_TABLE} WHERE name = ?", (draft_name,))
                conn.commit()
            if result.rowcount == 0:
                messagebox.showerror("Error", f"Draft '{draft_name}' not found.")
                return False
            self.set_status(f"Draft '{draft_name}' deleted.")
            return True
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to delete draft: {exc}")
            return False

    # ----------------------------------------------------------------- dialogs
    def _ask_string(self, title, prompt, initial=""):
        """A small themed modal text-input dialog. Returns str or None."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=self.theme["bg"])
        dialog.transient(self)
        dialog.resizable(False, False)

        result = {"value": None}
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=prompt, style="TLabel").pack(anchor="w", pady=(0, 8))

        var = tk.StringVar(value=initial)
        entry = ttk.Entry(frame, textvariable=var, width=36)
        entry.pack(fill="x")
        entry.focus_set()

        def ok():
            result["value"] = var.get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", style="Ghost.TButton",
                   command=cancel).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton",
                   command=ok).pack(side="right")
        entry.bind("<Return>", lambda e: ok())
        dialog.bind("<Escape>", lambda e: cancel())

        self._center_window_over(dialog)
        dialog.grab_set()
        self.wait_window(dialog)
        return result["value"]

    def set_status(self, message):
        self.status_var.set(message)

    # ------------------------------------------------------------------- theme
    def get_saved_theme_mode(self):
        """Return persisted theme mode, defaulting to dark."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (THEME_MODE_KEY,)
                ).fetchone()
                if row is None:
                    return "dark"
                parsed = str(row[0]).strip().lower()
                return "light" if parsed in {"0", "light"} else "dark"
        except sqlite3.Error:
            return "dark"

    def save_theme_mode(self, mode):
        value = 1 if mode == "dark" else 0
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO app_state (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (THEME_MODE_KEY, value),
                )
                conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to save theme preference: {exc}")

    def refresh_theme_toggle_icon(self):
        self.theme_toggle_var.set("☀" if self.theme_mode == "dark" else "☾")

    def toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        self.theme = THEMES[self.theme_mode]
        self._configure_styles()
        self.configure(bg=self.theme["bg"])
        if hasattr(self, "body_canvas"):
            self.body_canvas.configure(bg=self.theme["bg"])
        # re-theme any open calendar popup
        if self.date_window is not None and self.date_window.winfo_exists():
            self.date_window.configure(bg=self.theme["bg"])
        if self.drafts_manager_window is not None and self.drafts_manager_window.winfo_exists():
            self.drafts_manager_window.configure(bg=self.theme["bg"])
        self.refresh_theme_toggle_icon()
        self.save_theme_mode(self.theme_mode)

    # --------------------------------------------------------- invoice counter
    def refresh_invoice_number_field(self):
        """Pre-fill the invoice-number entry with the next number in sequence."""
        current = self.get_current_invoice_number()
        self.invoice_number_var.set("" if current is None else str(current + 1))

    def _fill_invoice_number_if_blank(self, event=None):
        """Snap a blank invoice-number field back to the next number in sequence."""
        if not self.invoice_number_var.get().strip():
            self.refresh_invoice_number_field()

    def _peek_invoice_number(self):
        """Resolve the invoice number without mutating storage.

        Returns (number, is_custom). A blank field means the next number in
        sequence; any explicit value is used as-is. Returns (None, False) if
        the field holds an invalid value.
        """
        raw = self.invoice_number_var.get().strip()
        if not raw:
            current = self.get_current_invoice_number()
            if current is None:
                messagebox.showerror("Error", "Invoice counter is unavailable.")
                return None, False
            return current + 1, False

        if not raw.isdigit() or int(raw) <= 0:
            messagebox.showerror("Error", "Invoice number must be a positive whole number.")
            return None, False
        return int(raw), True

    def _commit_invoice_number(self, number, is_custom):
        """Persist counter progress after a successful generation."""
        if is_custom:
            # never move the counter backwards, so future defaults stay unique
            self._set_last_invoice_number_at_least(number)
        else:
            # reserve the next number in sequence atomically
            self.get_next_invoice_number()

    def _set_last_invoice_number_at_least(self, number):
        """Set the stored counter to max(current, number)."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB, timeout=10) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (INVOICE_COUNTER_KEY,)
                ).fetchone()
                current = int(row[0]) if row else 0
                new_value = max(current, number)
                if row is None:
                    conn.execute("INSERT INTO app_state (key, value) VALUES (?, ?)",
                                 (INVOICE_COUNTER_KEY, new_value))
                else:
                    conn.execute("UPDATE app_state SET value = ? WHERE key = ?",
                                 (new_value, INVOICE_COUNTER_KEY))
                conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to update invoice counter: {exc}")

    def initialize_invoice_counter(self):
        """Initialize SQLite storage and migrate the legacy counter once."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_state (
                        key TEXT PRIMARY KEY,
                        value INTEGER NOT NULL
                    )
                    """
                )
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (INVOICE_COUNTER_KEY,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO app_state (key, value) VALUES (?, ?)",
                        (INVOICE_COUNTER_KEY, self._read_legacy_invoice_number()),
                    )

                theme_row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (THEME_MODE_KEY,)
                ).fetchone()
                if theme_row is None:
                    conn.execute(
                        "INSERT INTO app_state (key, value) VALUES (?, ?)",
                        (THEME_MODE_KEY, 1),
                    )
                conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to initialize invoice counter database: {exc}")

    def _read_legacy_invoice_number(self):
        if not os.path.exists(LEGACY_INVOICE_NUMBER_FILE):
            return 0
        try:
            with open(LEGACY_INVOICE_NUMBER_FILE, "r", encoding="utf-8") as file:
                raw = file.read().strip()
                parsed = int(raw) if raw else 0
                return parsed if parsed >= 0 else 0
        except (ValueError, OSError):
            return 0

    def get_next_invoice_number(self):
        """Atomically reserve and return the next invoice number."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB, timeout=10) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (INVOICE_COUNTER_KEY,)
                ).fetchone()
                current = int(row[0]) if row else 0
                next_value = current + 1
                if row is None:
                    conn.execute("INSERT INTO app_state (key, value) VALUES (?, ?)",
                                 (INVOICE_COUNTER_KEY, next_value))
                else:
                    conn.execute("UPDATE app_state SET value = ? WHERE key = ?",
                                 (next_value, INVOICE_COUNTER_KEY))
                conn.commit()
                return next_value
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to get next invoice number: {exc}")
            return 0

    def get_current_invoice_number(self):
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?", (INVOICE_COUNTER_KEY,)
                ).fetchone()
                return int(row[0]) if row else 0
        except sqlite3.Error:
            return None

    # --------------------------------------------------------- validation
    def _validate_required_fields(self):
        required = {
            "Company Name": self.company_name.get().strip(),
            "Address": self.address.get().strip(),
            "City": self.city_st_zip.get().strip(),
            "Phone No": self.phone_no.get().strip(),
            "Customer Name": self.customer_name.get().strip(),
            "Invoice Date": self.date.get().strip(),
            "Due Date": self.due_date.get().strip(),
            "Authorized Signatory": self.authorized_signatory.get().strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            messagebox.showerror("Error", "Please fill in: " + ", ".join(missing))
            return False
        return True

    def _collect_line_items(self):
        """Validate and return parsed line items plus the subtotal."""
        parsed = []
        subtotal = 0.0
        for index, item in enumerate(self.line_items, start=1):
            row_date = item["date"].get().strip()
            row_description = item["description"].get().strip()
            row_location = item["location"].get().strip()
            row_rate_raw = item["rate"].get().strip()

            if not any((row_date, row_description, row_location, row_rate_raw)):
                continue  # ignore fully blank rows
            if not row_description or not row_rate_raw:
                messagebox.showerror(
                    "Error", f"Line item {index}: Description and Rate are required.")
                return None, None
            try:
                row_rate = float(row_rate_raw)
            except ValueError:
                messagebox.showerror("Error", f"Line item {index}: Rate must be a number.")
                return None, None
            if row_rate < 0:
                messagebox.showerror("Error", f"Line item {index}: Rate cannot be negative.")
                return None, None
            parsed.append((row_date, row_description, row_location, row_rate))
            subtotal += row_rate

        if not parsed:
            messagebox.showerror("Error", "Please add at least one valid line item.")
            return None, None
        return parsed, subtotal

    # ----------------------------------------------------------- generation
    def generate_invoice(self):
        """Validate input and render the invoice PDF."""
        if not self._validate_required_fields():
            return
        parsed_items, subtotal = self._collect_line_items()
        if parsed_items is None:
            return

        if self.companyimage_file_name and not os.path.isfile(self.companyimage_file_name):
            messagebox.showerror("Error", f"Company logo not found: {self.companyimage_file_name}")
            return
        if self.signature_file_name and not os.path.isfile(self.signature_file_name):
            messagebox.showerror("Error", f"Signature image not found: {self.signature_file_name}")
            return

        # resolve the invoice number (user override or the next in sequence)
        invoice_number, is_custom = self._peek_invoice_number()
        if invoice_number is None:
            return

        os.makedirs("invoices", exist_ok=True)
        pdf_filename = f"invoices/Invoice_{invoice_number}.pdf"

        # guard against silently overwriting an existing invoice file
        if os.path.exists(pdf_filename) and not messagebox.askyesno(
            "Overwrite?", f"Invoice_{invoice_number}.pdf already exists. Overwrite it?"
        ):
            return

        try:
            self._draw_pdf(pdf_filename, invoice_number, parsed_items, subtotal)
        except Exception as exc:  # pragma: no cover - reportlab/runtime errors
            messagebox.showerror("Error", f"Failed to generate PDF: {exc}")
            return

        # advance the persistent counter now that the PDF is written
        self._commit_invoice_number(invoice_number, is_custom)
        self.refresh_invoice_number_field()
        self.set_status(f"Generated {pdf_filename}  •  Total {self._money(subtotal)}")
        messagebox.showinfo("Success", f"Invoice saved as {pdf_filename}.")
        webbrowser.open(os.path.abspath(pdf_filename))

    def _draw_pdf(self, path, invoice_number, items, subtotal):
        """Render the invoice PDF with ReportLab (original invoice layout)."""
        inv_canvas = canvas.Canvas(path, pagesize=A4)
        width, height = A4

        # draw the logo at the top left
        if self.companyimage_file_name:
            inv_canvas.drawImage(self.companyimage_file_name, 2 * cm, height - 3.5 * cm,
                                 width=4 * cm, height=2 * cm)

        # company details next to the logo
        inv_canvas.setFont("Helvetica", 10)
        inv_canvas.setFillColorRGB(0.6, 0.6, 0.6)  # Set fill color to light gray
        inv_canvas.drawRightString(width - 2 * cm, height - 2 * cm, self.company_name.get())
        inv_canvas.drawRightString(width - 2 * cm, height - 2.5 * cm, self.email.get())
        inv_canvas.drawRightString(width - 2 * cm, height - 3 * cm, f"{self.phone_no.get()}")
        inv_canvas.drawRightString(width - 2 * cm, height - 3.5 * cm, self.address.get())
        inv_canvas.drawRightString(width - 2 * cm, height - 4 * cm, self.city_st_zip.get())
        inv_canvas.setFillColorRGB(0, 0, 0)  # Reset fill color to black

        inv_canvas.setFont("Helvetica", 20)
        inv_canvas.setFillColorRGB(0, 0.6, 0.9)  # Set fill color to #00adeb
        inv_canvas.drawCentredString(width / 2, height - 5 * cm, "INVOICE")
        inv_canvas.setFillColorRGB(0, 0, 0)  # Reset fill color to black

        # invoice information
        inv_canvas.setFont("Helvetica-Bold", 10)
        inv_canvas.drawRightString(width - 2 * cm, height - 5 * cm, f"Invoice No.: {invoice_number}")
        inv_canvas.setFont("Helvetica", 10)
        inv_canvas.drawRightString(width - 2 * cm, height - 5.5 * cm, f"Due Date: {self.due_date.get()}")
        inv_canvas.drawRightString(width - 2 * cm, height - 6 * cm, f"Invoice Date: {self.date.get()}")

        # client Information
        inv_canvas.setFont("Helvetica-Bold", 10)
        inv_canvas.drawString(2 * cm, height - 5 * cm, "BILL TO:")
        inv_canvas.setFont("Helvetica", 10)
        inv_canvas.drawString(2 * cm, height - 5.5 * cm, f"{self.customer_name.get()}")
        inv_canvas.drawString(2 * cm, height - 6 * cm, f"{self.customer_email.get()}")
        inv_canvas.drawString(2 * cm, height - 6.5 * cm, f"{self.customer_address.get()}")
        inv_canvas.drawString(2 * cm, height - 7 * cm, f"{self.customer_city.get()}")

        inv_canvas.setStrokeColorRGB(0.8, 0.8, 0.8)  # Set stroke color to light gray
        inv_canvas.line(2 * cm, height - 8 * cm, width - 2 * cm, height - 8 * cm)

        inv_canvas.drawString(2 * cm, height - 8.5 * cm, "Date")
        inv_canvas.drawString(5 * cm, height - 8.5 * cm, "Description")
        inv_canvas.drawString(12 * cm, height - 8.5 * cm, "Location")
        inv_canvas.drawString(17 * cm, height - 8.5 * cm, "Rate")

        y_position = height - 9.5 * cm

        # print line items
        # light grey color background for every other item for better readability
        light_grey = Color(0.9, 0.9, 0.9)

        for index, item in enumerate(items):
            row_date, row_description, row_location, row_rate = item

            # keep rows from colliding with totals/signature section
            if y_position < 8 * cm:
                inv_canvas.showPage()
                y_position = height - 3 * cm

            # check if the index is even to set the light grey background
            if index % 2 != 0:
                inv_canvas.setFillColor(light_grey)
                inv_canvas.rect(1.8 * cm, y_position - 0.2 * cm, 17 * cm, .70 * cm, fill=1, stroke=0)

            # reset to default fill color (black) for text
            inv_canvas.setFillColor(Color(0, 0, 0))

            inv_canvas.drawString(2 * cm, y_position, row_date)
            inv_canvas.drawString(5 * cm, y_position, row_description)
            inv_canvas.drawString(12 * cm, y_position, row_location)
            inv_canvas.drawString(17 * cm, y_position, f"${row_rate:.2f}")

            # update y position for next line item
            y_position -= 1 * cm

        inv_canvas.setStrokeColorRGB(0.8, 0.8, 0.8)  # Set stroke color to light gray
        inv_canvas.line(2 * cm, y_position, width - 2 * cm, y_position)

        # print total
        inv_canvas.drawRightString(width - 6 * cm, y_position - 1 * cm, f"Total:")
        inv_canvas.setFont("Helvetica-Bold", 12)
        inv_canvas.setFillColorRGB(0, 0.6, 0.9)  # Set fill color to #00adeb
        inv_canvas.drawRightString(width - 3 * cm, y_position - 1 * cm, f"$ {subtotal:.2f}")
        inv_canvas.setFillColorRGB(0, 0, 0)  # Reset fill color to black

        inv_canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
        inv_canvas.line(width - 8 * cm, y_position - 1.5 * cm, width - 2 * cm, y_position - 1.5 * cm)

        # signature
        inv_canvas.drawRightString(width - 2 * cm, 2 * cm, f"Authorized Signatory: " + self.authorized_signatory.get())
        if self.signature_file_name:
            inv_canvas.drawImage(self.signature_file_name, width - 6 * cm, 2.5 * cm, width=6 * cm, height=2 * cm, mask='auto')

        # add note to the invoice
        inv_canvas.setFillColorRGB(0.5, 0.5, 0.5)  # Set fill color to light gray
        inv_canvas.setFont("Helvetica", 10)
        note_text = DEFAULT_NOTE

        note_lines = textwrap.wrap(note_text, width=90)

        for line in note_lines:
            inv_canvas.drawString(3 * cm, y_position - 3 * cm, line)
            y_position -= 0.5 * cm

        inv_canvas.showPage()
        inv_canvas.save()

    # ------------------------------------------------------------- geometry
    def _center_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _center_window_over(self, window):
        window.update_idletasks()
        w = window.winfo_width()
        h = window.winfo_height()
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 3
        window.geometry(f"+{max(0, x)}+{max(0, y)}")


if __name__ == "__main__":
    app = InvoiceGeneratorApp()
    app.mainloop()

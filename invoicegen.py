
"""
Invoice Generator
This class represents an application for generating invoices. It provides a
graphical user interface (GUI) for users to input company details, customer information, 
line items, and generate PDF invoices.

Attributes:
    company_name (tk.StringVar): The name of the company.
    address (tk.StringVar): The address of the company.
    city_st_zip (tk.StringVar): The city, state, and zip code of the company.
    phone_no (tk.StringVar): The phone number of the company.
    email (tk.StringVar): The email address of the company.
    customer_name (tk.StringVar): The name of the customer.
    customer_email (tk.StringVar): The email address of the customer.
    customer_address (tk.StringVar): The address of the customer.
    customer_city (tk.StringVar): The city of the customer.
    date (tk.StringVar): The date of the invoice.
    authorized_signatory (str): The authorized signatory of the company.
    line_items (list): A list of line items, each containing the date, description, location, and rate.
Methods:
    __init__(): Initializes the InvoiceGeneratorApp class.
    load_config(file_path): Loads configuration from a file and sets default values.
    create_widgets(): Creates the user interface widgets.
    create_label_and_entry(label_text, text_variable, y_position): Creates a label and entry widget pair.
    select_date(): Opens a calendar window for selecting a date.
    open_line_item_window(): Opens a window for entering line items.
    add_line_item_row(): Adds a new row for entering a line item.
    generate_invoice(): Generates an invoice PDF based on the entered information.
"""

# import required libraries
import os
import json
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkcalendar import Calendar
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
import webbrowser
import datetime
from datetime import timedelta
import textwrap


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

class InvoiceGeneratorApp(tk.Tk):
    def __init__(self):
        """
        Initializes the InvoiceGeneratorApp class.

        Args:
            None
        Returns:
            None
        """
        super().__init__()  # call constructor of the parent class
        # set title, and GUI of app window
        self.title("Invoice Generator")
        self.geometry("700x750")

        self.themes = {
            "dark": {
                "bg": "#1b1d24",
                "panel_bg": "#262a35",
                "fg": "#e8ecf4",
                "muted_fg": "#a6afc0",
                "entry_bg": "#2f3442",
                "entry_fg": "#f2f5fb",
                "button_bg": "#3b4254",
                "button_fg": "#f2f5fb",
                "accent_bg": "#5aa9ff",
                "accent_fg": "#0f1420",
                "danger_bg": "#b24a4a",
                "danger_active_bg": "#d65c5c",
                "accent_active_bg": "#83bfff",
                "border": "#434a5f",
            },
            "light": {
                "bg": "#f4f7fb",
                "panel_bg": "#ffffff",
                "fg": "#1d2532",
                "muted_fg": "#556179",
                "entry_bg": "#ffffff",
                "entry_fg": "#111827",
                "button_bg": "#d9e1f0",
                "button_fg": "#172033",
                "accent_bg": "#1f6feb",
                "accent_fg": "#ffffff",
                "danger_bg": "#c73a3a",
                "danger_active_bg": "#df5a5a",
                "accent_active_bg": "#4687ee",
                "border": "#b8c2d6",
            },
        }
        self.theme_mode = "dark"
        self.theme = self.themes[self.theme_mode]
        self.configure(bg=self.theme["bg"])

        # define defaults before config loading to avoid missing attributes on invalid config files
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

        # initialize variables via config file
        self.load_config("config.txt")

        # set current date
        today = datetime.date.today()
        self.date = tk.StringVar(value=today.strftime("%d %B %Y"))
        self.due_date = (today + timedelta(days=15)).strftime("%d %B %Y")

        # assume authorized signatory is the company name (self)
        self.authorized_signatory = self.company_name
        self.next_invoice_number_var = tk.StringVar(value="Invoice #: --")

        self.line_items = []  # To store each line item (Description, Qty, Unit Price, Total)
        self.line_item_window = None
        self.drafts_manager_window = None
        self.date_window = None
        self.theme_toggle_var = tk.StringVar(value="")

        # initialize persistent invoice counter storage before rendering widgets
        self.initialize_invoice_counter()
        self.theme_mode = self.get_saved_theme_mode()
        self.theme = self.themes[self.theme_mode]
        self.configure(bg=self.theme["bg"])
        self.initialize_drafts_storage()
        self.refresh_next_invoice_number_label()

        # Create the UI
        self.create_widgets()

    def load_config(self, file_path):
        """
            Load configuration from a file and set default values.
            Note: See README for config.txt file format.

            Args:
                file_path (str): The path to the configuration file.
            Returns:
                None
        """
        # confirm filepath exists
        if not os.path.isfile(file_path):
            messagebox.showerror("Error", f"Configuration file not found: {file_path}")
            return

        # read from config file to set default values
        with open(file_path, 'r') as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                # allow blank lines and comments in config.txt
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    messagebox.showwarning("Config Warning", f"Skipping invalid config line {line_number}: {line}")
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key not in CONFIG_KEYS:
                    continue

                if key == "companyimage_file_name":
                    self.companyimage_file_name = value
                elif key == "signature_file_name":
                    self.signature_file_name = value
                elif key == "company_name":
                    self.company_name = tk.StringVar(value=value)
                elif key == "address":
                    self.address = tk.StringVar(value=value)
                elif key == "city_st_zip":
                    self.city_st_zip = tk.StringVar(value=value)
                elif key == "phone_no":
                    self.phone_no = tk.StringVar(value=value)
                elif key == "email":
                    self.email = tk.StringVar(value=value)
                elif key == "customer_name":
                    self.customer_name = tk.StringVar(value=value)
                elif key == "customer_email":
                    self.customer_email = tk.StringVar(value=value)
                elif key == "customer_address":
                    self.customer_address = tk.StringVar(value=value)
                elif key == "customer_city":
                    self.customer_city = tk.StringVar(value=value)

    def _validate_required_fields(self):
        """Validate required top-level form fields before invoice generation."""
        required_fields = {
            "Company Name": self.company_name.get().strip(),
            "Address": self.address.get().strip(),
            "City": self.city_st_zip.get().strip(),
            "Date": self.date.get().strip(),
            "Customer Name": self.customer_name.get().strip(),
            "Phone No": self.phone_no.get().strip(),
            "Authorized Signatory": self.authorized_signatory.get().strip(),
        }

        missing_fields = [name for name, value in required_fields.items() if not value]
        if missing_fields:
            messagebox.showerror("Error", f"Please fill in all fields: {', '.join(missing_fields)}")
            return False
        return True

    def _validate_line_items(self):
        """Validate and normalize line items, returning parsed rows and subtotal."""
        parsed_items = []
        subtotal = 0.0

        for index, item in enumerate(self.line_items, start=1):
            date, description, location, rate = item
            row_date = date.get().strip()
            row_description = description.get().strip()
            row_location = location.get().strip()
            row_rate_raw = rate.get().strip()

            # ignore fully empty rows so users can leave an extra blank row in the UI
            if not row_date and not row_description and not row_location and not row_rate_raw:
                continue

            if not row_description or not row_rate_raw:
                messagebox.showerror("Error", f"Line item {index}: Description and Rate are required.")
                return None, None

            try:
                row_rate = float(row_rate_raw)
            except ValueError:
                messagebox.showerror("Error", f"Line item {index}: Rate must be a valid number.")
                return None, None

            if row_rate < 0:
                messagebox.showerror("Error", f"Line item {index}: Rate cannot be negative.")
                return None, None

            parsed_items.append((row_date, row_description, row_location, row_rate))
            subtotal += row_rate

        if not parsed_items:
            messagebox.showerror("Error", "Please add at least one valid line item.")
            return None, None

        return parsed_items, subtotal

    def create_widgets(self):
        """
            Create the user interface widgets for the application.

            Args:
                None
            Returns:
                None
        """

        # Company Details
        tk.Label(
            self,
            text="Company Details",
            font=("Arial", 20, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["fg"],
        ).pack(pady=10)
        tk.Label(
            self,
            textvariable=self.next_invoice_number_var,
            font=("Arial", 11, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["muted_fg"],
        ).pack()

        theme_button = tk.Button(
            self,
            textvariable=self.theme_toggle_var,
            command=self.toggle_theme,
            font=("Arial", 12, "bold"),
            width=3,
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        theme_button.theme_role = "default"
        theme_button.place(x=640, y=10, width=45, height=30)
        self.refresh_theme_toggle_icon()

        # create labels and entry widgets for inputting company details
        self.create_label_and_entry("Company Name", self.company_name, 80)
        self.create_label_and_entry("Address", self.address, 140)
        self.create_label_and_entry("City", self.city_st_zip, 200)
        self.create_label_and_entry("Phone No", self.phone_no, 380)
        self.create_label_and_entry("Customer Name", self.customer_name, 440)
        self.create_label_and_entry("Authorized Signatory", self.authorized_signatory, 500)

        # client details
        tk.Label(
            self,
            text="Date",
            font=("Arial", 12),
            bg=self.theme["bg"],
            fg=self.theme["fg"],
        ).place(x=50, y=320)
        tk.Entry(
            self,
            textvariable=self.date,
            font=("Arial", 12),
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).place(x=250, y=320, width=300, height=30)
        tk.Button(
            self,
            text="Select Date",
            font=("Arial", 12),
            command=self.select_date,
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        ).place(x=570, y=320)

        # option to enter line items
        enter_line_items_button = tk.Button(
            self,
            text="Enter Line Items",
            command=self.open_line_item_window,
            font=("Arial", 12),
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        enter_line_items_button.theme_role = "default"
        enter_line_items_button.place(x=50, y=640, width=200, height=40)

        # button to generate invoice
        generate_button = tk.Button(
            self,
            text="Generate Invoice",
            command=self.generate_invoice,
            font=("Arial", 12),
            bg=self.theme["accent_bg"],
            fg=self.theme["accent_fg"],
            activebackground=self.theme["accent_active_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        generate_button.theme_role = "accent"
        generate_button.place(x=300, y=640, width=200, height=40)

        # draft controls
        save_draft_button = tk.Button(
            self,
            text="Save Draft",
            command=self.prompt_save_draft,
            font=("Arial", 11),
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        save_draft_button.theme_role = "default"
        save_draft_button.place(x=50, y=690, width=200, height=35)

        manage_drafts_button = tk.Button(
            self,
            text="Manage Drafts",
            command=self.open_drafts_manager,
            font=("Arial", 11),
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        manage_drafts_button.theme_role = "default"
        manage_drafts_button.place(x=300, y=690, width=200, height=35)

    def create_label_and_entry(self, label_text, text_variable, y_position):
        """
            Create a label and entry widget pair for inputting information.

            Args:
                label_text (str): The text for the label.
                text_variable (tk.StringVar): The variable to store the input value.
                y_position (int): The y-position of the label and entry widgets.
            Returns:
                None
        """

        # create label and entry widgets
        tk.Label(
            self,
            text=label_text,
            font=("Arial", 12),
            bg=self.theme["bg"],
            fg=self.theme["fg"],
        ).place(x=50, y=y_position)
        tk.Entry(
            self,
            textvariable=text_variable,
            font=("Arial", 12),
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).place(x=250, y=y_position, width=300, height=30)

    def select_date(self):
        """
            Opens calendar window for selecting a date.
        
            Args:
                None
            Returns:
                None
        """
        top = tk.Toplevel(self)
        self.date_window = top
        top.geometry("400x400")
        top.configure(bg=self.theme["bg"])

        def on_close_date_window():
            self.date_window = None
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_close_date_window)

        today = datetime.date.today()
        cal = Calendar(
            top,
            selectmode='day',
            year=today.year,
            month=today.month,
            day=today.day,
            background=self.theme["panel_bg"],
            foreground=self.theme["fg"],
            headersbackground=self.theme["entry_bg"],
            headersforeground=self.theme["fg"],
            normalbackground=self.theme["panel_bg"],
            normalforeground=self.theme["fg"],
            weekendbackground=self.theme["entry_bg"],
            weekendforeground=self.theme["fg"],
            selectbackground=self.theme["accent_bg"],
            selectforeground=self.theme["accent_fg"],
            bordercolor=self.theme["border"],
        )
        cal.pack(pady=20)

        def set_date():
            # set invoice date
            date_str = cal.get_date()
            date_adj = datetime.datetime.strptime(date_str, "%m/%d/%y")
            self.date.set(date_adj.strftime("%d %B %Y"))

            # adjust due date
            self.due_date = (date_adj + timedelta(days=15)).strftime("%d %B %Y")
            self.date_window = None
            top.destroy()

        set_date_button = tk.Button(
            top,
            text="Set Date",
            command=set_date,
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        set_date_button.theme_role = "default"
        set_date_button.pack(pady=20)

    def open_line_item_window(self):
        """
            Opens a window for entering line items.

            Args:
                None
            Returns:
                None
        """

        # Reuse the existing line items window if it's already open.
        if self.line_item_window is not None and self.line_item_window.winfo_exists():
            self.line_item_window.lift()
            self.line_item_window.focus_force()
            return

        # create GUI window for entering line items
        self.line_item_window = tk.Toplevel(self)
        self.line_item_window.title("Line Items")
        self.line_item_window.geometry("800x600")
        self.line_item_window.configure(bg=self.theme["bg"])
        self.line_item_window.protocol("WM_DELETE_WINDOW", self.close_line_item_window)

        # create labels for line items
        tk.Label(self.line_item_window, text="Date", font=("Arial", 12), bg=self.theme["bg"], fg=self.theme["fg"]).grid(row=0, column=0, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Description", font=("Arial", 12), bg=self.theme["bg"], fg=self.theme["fg"]).grid(row=0, column=1, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Location", font=("Arial", 12), bg=self.theme["bg"], fg=self.theme["fg"]).grid(row=0, column=2, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Rate", font=("Arial", 12), bg=self.theme["bg"], fg=self.theme["fg"]).grid(row=0, column=3, padx=10, pady=10)

        if self.line_items:
            for row_index, item in enumerate(self.line_items, start=1):
                date, description, location, rate = item
                self.render_line_item_row(row_index, date, description, location, rate)
        else:
            # add initial row for line item
            self.add_line_item_row()

        # button to add new line item row
        add_line_button = tk.Button(
            self.line_item_window,
            text="+ Add Line",
            command=self.add_line_item_row,
            font=("Arial", 12),
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        add_line_button.theme_role = "default"
        add_line_button.grid(row=999, column=0, columnspan=4, pady=20)

    def add_line_item_row(self):
        """
            Adds a new row for entering a line item.

            Args:
                None
            Returns:
                None
        """
        if self.line_item_window is None or not self.line_item_window.winfo_exists():
            # Avoid stale state updates when the line item window is closed.
            return

        # initialize variables for line item
        row_index = len(self.line_items) + 1
        date = tk.StringVar()
        description = tk.StringVar()
        location = tk.StringVar()
        rate = tk.StringVar()

        # append line item to list before rendering
        self.line_items.append((date, description, location, rate))

        self.render_line_item_row(row_index, date, description, location, rate)

    def render_line_item_row(self, row_index, date, description, location, rate):
        """Render one line item row in the line item window."""
        if self.line_item_window is None or not self.line_item_window.winfo_exists():
            return

        # create entry widgets for each line item
        tk.Entry(
            self.line_item_window,
            textvariable=date,
            font=("Arial", 12),
            width=15,
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).grid(row=row_index, column=0, padx=10, pady=10)
        tk.Entry(
            self.line_item_window,
            textvariable=description,
            font=("Arial", 12),
            width=30,
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).grid(row=row_index, column=1, padx=10, pady=10)
        tk.Entry(
            self.line_item_window,
            textvariable=location,
            font=("Arial", 12),
            width=20,
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).grid(row=row_index, column=2, padx=10, pady=10)
        tk.Entry(
            self.line_item_window,
            textvariable=rate,
            font=("Arial", 12),
            width=10,
            bg=self.theme["entry_bg"],
            fg=self.theme["entry_fg"],
            insertbackground=self.theme["entry_fg"],
            relief="flat",
        ).grid(row=row_index, column=3, padx=10, pady=10)

    def cache_line_items_progress(self):
        """Persist current line-item values in memory for later editing."""
        sanitized_items = []
        for row in self.line_items:
            if not row or len(row) != 4:
                continue

            date, description, location, rate = row
            sanitized_items.append(
                (
                    tk.StringVar(value=date.get().strip()),
                    tk.StringVar(value=description.get().strip()),
                    tk.StringVar(value=location.get().strip()),
                    tk.StringVar(value=rate.get().strip()),
                )
            )

        self.line_items = sanitized_items

    def close_line_item_window(self):
        """Close line item window and keep in-memory line-item state."""
        if self.line_item_window is None or not self.line_item_window.winfo_exists():
            self.line_item_window = None
            return

        # Save current content before closing to prevent accidental data loss.
        self.cache_line_items_progress()

        self.line_item_window.destroy()
        self.line_item_window = None

    def initialize_drafts_storage(self):
        """Initialize storage for invoice drafts."""
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
        """Prompt for draft name and save current invoice state."""
        draft_name = simpledialog.askstring("Save Draft", "Enter a draft name:")
        if not draft_name:
            return

        draft_name = draft_name.strip()
        if not draft_name:
            messagebox.showerror("Error", "Draft name cannot be empty.")
            return

        self.save_draft(draft_name)

    def save_draft(self, draft_name):
        """Save current form and line item state to drafts storage."""
        draft_payload = {
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
            "due_date": self.due_date,
            "authorized_signatory": self.authorized_signatory.get().strip(),
            "line_items": [
                {
                    "date": date.get().strip(),
                    "description": description.get().strip(),
                    "location": location.get().strip(),
                    "rate": rate.get().strip(),
                }
                for date, description, location, rate in self.line_items
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
                    (draft_name, json.dumps(draft_payload), now_iso),
                )
                conn.commit()
            messagebox.showinfo("Success", f"Draft '{draft_name}' saved.")
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to save draft: {exc}")

    def open_drafts_manager(self):
        """Open draft manager window for loading and deleting drafts."""
        manager = tk.Toplevel(self)
        self.drafts_manager_window = manager
        manager.title("Drafts")
        manager.geometry("500x400")
        manager.configure(bg=self.theme["bg"])

        def on_close_drafts_manager():
            self.drafts_manager_window = None
            manager.destroy()

        manager.protocol("WM_DELETE_WINDOW", on_close_drafts_manager)

        tk.Label(
            manager,
            text="Saved Drafts",
            font=("Arial", 14, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["fg"],
        ).pack(pady=10)

        listbox = tk.Listbox(
            manager,
            font=("Arial", 11),
            width=60,
            height=12,
            bg=self.theme["panel_bg"],
            fg=self.theme["fg"],
            selectbackground=self.theme["accent_bg"],
            selectforeground=self.theme["accent_fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )
        listbox.pack(padx=10, pady=10)

        draft_names = []

        def refresh_drafts_list():
            listbox.delete(0, tk.END)
            draft_names.clear()

            for name, updated_at in self.get_saved_drafts():
                draft_names.append(name)
                listbox.insert(tk.END, f"{name}  (updated: {updated_at})")

            if not draft_names:
                listbox.insert(tk.END, "No drafts found")

        def get_selected_draft_name():
            if not listbox.curselection():
                return None
            selected_index = listbox.curselection()[0]
            if selected_index >= len(draft_names):
                return None
            return draft_names[selected_index]

        def load_selected_draft():
            selected_name = get_selected_draft_name()
            if not selected_name:
                messagebox.showerror("Error", "Select a draft to load.")
                return

            if self.load_draft(selected_name):
                messagebox.showinfo("Success", f"Draft '{selected_name}' loaded.")
                manager.destroy()

        def delete_selected_draft():
            selected_name = get_selected_draft_name()
            if not selected_name:
                messagebox.showerror("Error", "Select a draft to delete.")
                return

            confirmed = messagebox.askyesno("Confirm Delete", f"Delete draft '{selected_name}'?")
            if not confirmed:
                return

            if self.delete_draft(selected_name):
                refresh_drafts_list()

        button_row = tk.Frame(manager, bg=self.theme["bg"])
        button_row.pack(pady=10)

        load_button = tk.Button(
            button_row,
            text="Load",
            command=load_selected_draft,
            width=12,
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        load_button.theme_role = "default"
        load_button.grid(row=0, column=0, padx=5)

        delete_button = tk.Button(
            button_row,
            text="Delete",
            command=delete_selected_draft,
            width=12,
            bg=self.theme["danger_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["danger_active_bg"],
            activeforeground=self.theme["button_fg"],
            relief="flat",
        )
        delete_button.theme_role = "danger"
        delete_button.grid(row=0, column=1, padx=5)

        refresh_button = tk.Button(
            button_row,
            text="Refresh",
            command=refresh_drafts_list,
            width=12,
            bg=self.theme["button_bg"],
            fg=self.theme["button_fg"],
            activebackground=self.theme["accent_bg"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
        )
        refresh_button.theme_role = "default"
        refresh_button.grid(row=0, column=2, padx=5)

        refresh_drafts_list()

    def get_saved_drafts(self):
        """Return a list of saved draft names and timestamps."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                rows = conn.execute(
                    f"SELECT name, updated_at FROM {DRAFTS_TABLE} ORDER BY updated_at DESC"
                ).fetchall()
                return rows
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to fetch drafts: {exc}")
            return []

    def load_draft(self, draft_name):
        """Load draft values into the current form and line item state."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                row = conn.execute(
                    f"SELECT payload FROM {DRAFTS_TABLE} WHERE name = ?",
                    (draft_name,),
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
        self.due_date = payload.get("due_date", self.due_date)
        self.authorized_signatory.set(payload.get("authorized_signatory", ""))

        self.line_items = []
        for item in payload.get("line_items", []):
            self.line_items.append(
                (
                    tk.StringVar(value=item.get("date", "")),
                    tk.StringVar(value=item.get("description", "")),
                    tk.StringVar(value=item.get("location", "")),
                    tk.StringVar(value=item.get("rate", "")),
                )
            )

        # if line items window is open, rebuild it with loaded rows
        if self.line_item_window is not None and self.line_item_window.winfo_exists():
            self.line_item_window.destroy()
            self.open_line_item_window()

        return True

    def delete_draft(self, draft_name):
        """Delete a draft by name."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                result = conn.execute(
                    f"DELETE FROM {DRAFTS_TABLE} WHERE name = ?",
                    (draft_name,),
                )
                conn.commit()

            if result.rowcount == 0:
                messagebox.showerror("Error", f"Draft '{draft_name}' not found.")
                return False

            messagebox.showinfo("Success", f"Draft '{draft_name}' deleted.")
            return True
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to delete draft: {exc}")
            return False

    def generate_invoice(self):
        """
            Generates an invoice PDF based on the entered information.

            Args:
                None
            Returns:
                None
        """

        if not self._validate_required_fields():
            return

        parsed_items, subtotal = self._validate_line_items()
        if parsed_items is None:
            return

        # ensure output directory exists
        os.makedirs("invoices", exist_ok=True)

        if self.companyimage_file_name and not os.path.isfile(self.companyimage_file_name):
            messagebox.showerror("Error", f"Company logo not found: {self.companyimage_file_name}")
            return

        if self.signature_file_name and not os.path.isfile(self.signature_file_name):
            messagebox.showerror("Error", f"Signature image not found: {self.signature_file_name}")
            return

        # reserve the next invoice number from persistent counter storage
        invoice_number = self.get_next_invoice_number()
        if invoice_number <= 0:
            return

        pdf_filename = f"invoices/Invoice_{invoice_number}.pdf"

        # generate PDF to begin filling contents
        inv_canvas = canvas.Canvas(pdf_filename, pagesize=A4)
        width, height = A4

        # draw the logo at the top left
        if self.companyimage_file_name:
            inv_canvas.drawImage(self.companyimage_file_name, 2 * cm, height - 3.5 * cm, width=4 * cm, height=2 * cm)

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
        inv_canvas.drawRightString(width - 2 * cm, height - 5.5 * cm, f"{self.date.get()}")

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

        for index, item in enumerate(parsed_items):
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

        inv_canvas.setFont("Helvetica", 10)
        inv_canvas.setFont("Helvetica-Bold", 10)
        inv_canvas.drawRightString(width - 5.7 * cm, y_position - 2 * cm, "Due Date:")
        inv_canvas.setFont("Helvetica", 10)
        inv_canvas.drawRightString(width - 2.5 * cm, y_position - 2 * cm, f"{self.due_date}")

        # signature
        inv_canvas.drawRightString(width - 2 * cm, 2 * cm, f"Authorized Signatory: "+ self.authorized_signatory.get())
        if self.signature_file_name:
            inv_canvas.drawImage(self.signature_file_name, width - 6 * cm, 2.5 * cm, width=6 * cm, height=2 * cm, mask='auto')

        # add note to the invoice
        inv_canvas.setFillColorRGB(0.5, 0.5, 0.5)  # Set fill color to light gray
        inv_canvas.setFont("Helvetica", 10)
        note_text = f"Your business is greatly appreciated."

        note_lines = textwrap.wrap(note_text, width=90)

        for line in note_lines:
            inv_canvas.drawString(3 * cm, y_position - 3 * cm, line)
            y_position -= 0.5 * cm

        inv_canvas.showPage()
        inv_canvas.save()

        messagebox.showinfo("Success", f"Invoice generated successfully and saved as {pdf_filename}.")

        self.destroy()

        # Open the PDF in the default viewer
        webbrowser.open(os.path.abspath(pdf_filename))

    def refresh_next_invoice_number_label(self):
        """Update UI label with the upcoming invoice number."""
        current_invoice_number = self.get_current_invoice_number()
        if current_invoice_number is None:
            self.next_invoice_number_var.set("Invoice #: unavailable")
            return
        self.next_invoice_number_var.set(f"Invoice #: {current_invoice_number + 1}")

    def initialize_invoice_counter(self):
        """
            Initialize SQLite storage for invoice number tracking.
            If first run, migrate the value from legacy invoice_number.txt.

            Args:
                None
            Returns:
                None
        """
        db_path = INVOICE_COUNTER_DB

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_state (
                        key TEXT PRIMARY KEY,
                        value INTEGER NOT NULL
                    )
                    """
                )

                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?",
                    (INVOICE_COUNTER_KEY,),
                ).fetchone()

                if row is None:
                    legacy_value = self._read_legacy_invoice_number()
                    conn.execute(
                        "INSERT INTO app_state (key, value) VALUES (?, ?)",
                        (INVOICE_COUNTER_KEY, legacy_value),
                    )

                theme_row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?",
                    (THEME_MODE_KEY,),
                ).fetchone()
                if theme_row is None:
                    conn.execute(
                        "INSERT INTO app_state (key, value) VALUES (?, ?)",
                        (THEME_MODE_KEY, 1),
                    )

                    conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to initialize invoice counter database: {exc}")

    def get_saved_theme_mode(self):
        """Get persisted theme mode; defaults to dark on missing or invalid values."""
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?",
                    (THEME_MODE_KEY,),
                ).fetchone()
                if row is None:
                    return "dark"

                parsed = str(row[0]).strip().lower()
                if parsed in {"0", "light"}:
                    return "light"
                return "dark"
        except sqlite3.Error:
            return "dark"

    def save_theme_mode(self, mode):
        """Persist current theme mode to SQLite app state."""
        value = 1 if mode == "dark" else 0
        try:
            with sqlite3.connect(INVOICE_COUNTER_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO app_state (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (THEME_MODE_KEY, value),
                )
                conn.commit()
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to save theme preference: {exc}")

    def refresh_theme_toggle_icon(self):
        """Show moon in light mode and sun in dark mode as toggle hint."""
        self.theme_toggle_var.set("☀" if self.theme_mode == "dark" else "☾")

    def toggle_theme(self):
        """Switch between dark and light themes and persist selection."""
        next_mode = "light" if self.theme_mode == "dark" else "dark"
        self.apply_theme(next_mode, persist=True)

    def apply_theme(self, mode, persist=False):
        """Apply theme palette to existing widgets and open windows."""
        self.theme_mode = mode if mode in self.themes else "dark"
        self.theme = self.themes[self.theme_mode]
        self._apply_theme_to_window(self)

        for window_ref in (self.line_item_window, self.drafts_manager_window, self.date_window):
            if window_ref is not None and window_ref.winfo_exists():
                self._apply_theme_to_window(window_ref)

        self.refresh_theme_toggle_icon()
        if persist:
            self.save_theme_mode(self.theme_mode)

    def _apply_button_theme(self, button_widget):
        """Apply themed button colors, honoring special roles."""
        role = getattr(button_widget, "theme_role", "default")
        button_bg = self.theme["button_bg"]
        button_fg = self.theme["button_fg"]
        active_bg = self.theme["accent_bg"]
        active_fg = self.theme["accent_fg"]

        if role == "accent":
            button_bg = self.theme["accent_bg"]
            button_fg = self.theme["accent_fg"]
            active_bg = self.theme["accent_active_bg"]
            active_fg = self.theme["accent_fg"]
        elif role == "danger":
            button_bg = self.theme["danger_bg"]
            button_fg = self.theme["button_fg"]
            active_bg = self.theme["danger_active_bg"]
            active_fg = self.theme["button_fg"]

        button_widget.configure(
            bg=button_bg,
            fg=button_fg,
            activebackground=active_bg,
            activeforeground=active_fg,
        )

    def _apply_theme_to_window(self, root_widget):
        """Recursively apply current theme to widgets in a window."""
        root_widget.configure(bg=self.theme["bg"])

        def walk(widget):
            class_name = widget.winfo_class()

            try:
                if isinstance(widget, Calendar):
                    widget.configure(
                        background=self.theme["panel_bg"],
                        foreground=self.theme["fg"],
                        headersbackground=self.theme["entry_bg"],
                        headersforeground=self.theme["fg"],
                        normalbackground=self.theme["panel_bg"],
                        normalforeground=self.theme["fg"],
                        weekendbackground=self.theme["entry_bg"],
                        weekendforeground=self.theme["fg"],
                        selectbackground=self.theme["accent_bg"],
                        selectforeground=self.theme["accent_fg"],
                        bordercolor=self.theme["border"],
                    )
                elif class_name in {"Tk", "Toplevel", "Frame"}:
                    widget.configure(bg=self.theme["bg"])
                elif class_name == "Label":
                    widget.configure(bg=self.theme["bg"], fg=self.theme["fg"])
                elif class_name == "Entry":
                    widget.configure(
                        bg=self.theme["entry_bg"],
                        fg=self.theme["entry_fg"],
                        insertbackground=self.theme["entry_fg"],
                    )
                elif class_name == "Button":
                    self._apply_button_theme(widget)
                elif class_name == "Listbox":
                    widget.configure(
                        bg=self.theme["panel_bg"],
                        fg=self.theme["fg"],
                        selectbackground=self.theme["accent_bg"],
                        selectforeground=self.theme["accent_fg"],
                        highlightbackground=self.theme["border"],
                    )
            except tk.TclError:
                pass

            for child in widget.winfo_children():
                walk(child)

        walk(root_widget)

    def _read_legacy_invoice_number(self):
        """Read legacy invoice_number.txt value for one-time migration."""
        if not os.path.exists(LEGACY_INVOICE_NUMBER_FILE):
            return 0

        try:
            with open(LEGACY_INVOICE_NUMBER_FILE, "r") as file:
                raw_value = file.read().strip()
                parsed = int(raw_value) if raw_value else 0
                return parsed if parsed >= 0 else 0
        except (ValueError, OSError):
            return 0

    def get_next_invoice_number(self):
        """
            Get the next invoice number from SQLite persistent storage.

            Args:
                None
            Returns:
                int: The next invoice number.
        """
        db_path = INVOICE_COUNTER_DB

        try:
            with sqlite3.connect(db_path, timeout=10) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?",
                    (INVOICE_COUNTER_KEY,),
                ).fetchone()

                current_value = int(row[0]) if row else 0
                next_value = current_value + 1

                if row is None:
                    conn.execute(
                        "INSERT INTO app_state (key, value) VALUES (?, ?)",
                        (INVOICE_COUNTER_KEY, next_value),
                    )
                else:
                    conn.execute(
                        "UPDATE app_state SET value = ? WHERE key = ?",
                        (next_value, INVOICE_COUNTER_KEY),
                    )

                conn.commit()
                return next_value
        except sqlite3.Error as exc:
            messagebox.showerror("Error", f"Failed to get next invoice number: {exc}")
            return 0

    def get_current_invoice_number(self):
        """Return the last used invoice number from SQLite storage."""
        db_path = INVOICE_COUNTER_DB

        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = ?",
                    (INVOICE_COUNTER_KEY,),
                ).fetchone()
                return int(row[0]) if row else 0
        except sqlite3.Error:
            return None


if __name__ == "__main__":
    app = InvoiceGeneratorApp()
    app.mainloop()


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
import tkinter as tk
from tkinter import filedialog, messagebox
from tkcalendar import Calendar
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
import webbrowser
import datetime
from datetime import timedelta
import textwrap

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
        self.configure(bg='white')

        # initialize variables via config file
        self.load_config("config.txt")

        # set current date
        today = datetime.date.today()
        self.date = tk.StringVar(value=today.strftime("%d %B %Y"))
        self.due_date = (today + timedelta(days=15)).strftime("%d %B %Y")

        # assume authorized signatory is the company name (self)
        self.authorized_signatory = self.company_name

        self.line_items = []  # To store each line item (Description, Qty, Unit Price, Total)

        # Create the UI
        self.create_widgets()

        # verify the invoice number file exists
        self.verify_invoice_number_file()

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
            for line in file:
                key, value = line.strip().split('=', 1)
                value = value.strip()

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

    def create_widgets(self):
        """
            Create the user interface widgets for the application.

            Args:
                None
            Returns:
                None
        """

        # Company Details
        tk.Label(self, text="Company Details", font=("Arial", 20, "bold"), bg="white", fg="black").pack(pady=10)

        # create labels and entry widgets for inputting company details
        self.create_label_and_entry("Company Name", self.company_name, 80)
        self.create_label_and_entry("Address", self.address, 140)
        self.create_label_and_entry("City", self.city_st_zip, 200)
        self.create_label_and_entry("Phone No", self.phone_no, 380)
        self.create_label_and_entry("Customer Name", self.customer_name, 440)
        self.create_label_and_entry("Authorized Signatory", self.authorized_signatory, 500)

        # client details
        tk.Label(self, text="Date", font=("Arial", 12), bg="white", fg="black").place(x=50, y=320)
        tk.Entry(self, textvariable=self.date, font=("Arial", 12)).place(x=250, y=320, width=300, height=30)
        tk.Button(self, text="Select Date", font=("Arial", 12), command=self.select_date).place(x=570, y=320)

        # option to enter line items
        tk.Button(self, text="Enter Line Items", command=self.open_line_item_window, font=("Arial", 12), bg="black", fg="white").place(x=50, y=640, width=200, height=40)

        # button to generate invoice
        tk.Button(self, text="Generate Invoice", command=self.generate_invoice, font=("Arial", 12), bg="black", fg="white").place(x=300, y=640, width=200, height=40)

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
        tk.Label(self, text=label_text, font=("Arial", 12), bg="white", fg="black").place(x=50, y=y_position)
        tk.Entry(self, textvariable=text_variable, font=("Arial", 12)).place(x=250, y=y_position, width=300, height=30)

    def select_date(self):
        """
            Opens calendar window for selecting a date.
        
            Args:
                None
            Returns:
                None
        """
        top = tk.Toplevel(self)
        top.geometry("400x400")

        cal = Calendar(top, selectmode='day', year=2024, month=8, day=1)
        cal.pack(pady=20)

        def set_date():
            # set invoice date
            date_str = cal.get_date()
            date_adj = datetime.datetime.strptime(date_str, "%m/%d/%y")
            self.date.set(date_adj.strftime("%d %B %Y"))

            # adjust due date
            self.due_date = (date_adj + timedelta(days=15)).strftime("%d %B %Y")
            top.destroy()

        tk.Button(top, text="Set Date", command=set_date).pack(pady=20)

    def open_line_item_window(self):
        """
            Opens a window for entering line items.

            Args:
                None
            Returns:
                None
        """

        # create GUI window for entering line items
        self.line_item_window = tk.Toplevel(self)
        self.line_item_window.title("Line Items")
        self.line_item_window.geometry("800x600")
        self.line_item_window.configure(bg='white')

        # create labels for line items
        tk.Label(self.line_item_window, text="Date", font=("Arial", 12), bg="white").grid(row=0, column=0, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Description", font=("Arial", 12), bg="white").grid(row=0, column=1, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Location", font=("Arial", 12), bg="white").grid(row=0, column=2, padx=10, pady=10)
        tk.Label(self.line_item_window, text="Rate", font=("Arial", 12), bg="white").grid(row=0, column=3, padx=10, pady=10)

        # add initial row for line item
        self.add_line_item_row()

        # button to add new line item row
        tk.Button(self.line_item_window, text="+ Add Line", command=self.add_line_item_row, font=("Arial", 12), bg="black", fg="white").grid(row=999, column=0, columnspan=4, pady=20)

    def add_line_item_row(self):
        """
            Adds a new row for entering a line item.

            Args:
                None
            Returns:
                None
        """
        # initialize variables for line item
        row_index = len(self.line_items) + 1
        date = tk.StringVar()
        description = tk.StringVar()
        location = tk.StringVar()
        rate = tk.StringVar()

        # create entry widgets for each line item
        tk.Entry(self.line_item_window, textvariable=date, font=("Arial", 12), width=15).grid(row=row_index, column=0, padx=10, pady=10)
        tk.Entry(self.line_item_window, textvariable=description, font=("Arial", 12), width=30).grid(row=row_index, column=1, padx=10, pady=10)
        tk.Entry(self.line_item_window, textvariable=location, font=("Arial", 12), width=20).grid(row=row_index, column=2, padx=10, pady=10)
        tk.Entry(self.line_item_window, textvariable=rate, font=("Arial", 12), width=10).grid(row=row_index, column=3, padx=10, pady=10)

        # append line item to list
        self.line_items.append((date, description, location, rate))

    def generate_invoice(self):
        """
            Generates an invoice PDF based on the entered information.

            Args:
                None
            Returns:
                None
        """

        # Check if all fields are filled, return error if not
        if not self.company_name.get() or not self.address.get() or not self.city_st_zip.get() or not self.date.get() or not self.customer_name.get() or not self.phone_no.get() or not self.authorized_signatory.get():
            messagebox.showerror("Error", "Please fill in all fields.")
            return

        # get next invoice number from file, or create file if it doesn't exist
        invoice_number = self.get_next_invoice_number()
        pdf_filename = f"invoices/Invoice_{invoice_number}.pdf"

        # generate PDF to begin filling contents
        inv_canvas = canvas.Canvas(pdf_filename, pagesize=A4)
        width, height = A4

        # draw the logo at the top left
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

        subtotal : float = 0

        # print line items
        # light grey color background for every other item for better readability
        light_grey = Color(0.9, 0.9, 0.9)

        for index, item in enumerate(self.line_items):
            date, description, location, rate = item

            # check if the index is even to set the light grey background
            if index % 2 != 0:
                inv_canvas.setFillColor(light_grey)
                inv_canvas.rect(1.8 * cm, y_position - 0.2 * cm, 17 * cm, .70 * cm, fill=1, stroke=0)

            # reset to default fill color (black) for text
            inv_canvas.setFillColor(Color(0, 0, 0))

            inv_canvas.drawString(2 * cm, y_position, date.get())
            inv_canvas.drawString(5 * cm, y_position, description.get())
            inv_canvas.drawString(12 * cm, y_position, location.get())
            inv_canvas.drawString(17 * cm, y_position, "$" + rate.get())

            # increment totals
            subtotal += float(rate.get())
            
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

    def verify_invoice_number_file(self):
        """
            verify the invoice number file exists.

            Args:
                None
            Returns:
                None
        """
        if not os.path.exists("invoice_number.txt"):
            with open("invoice_number.txt", "w") as f:
                f.write("0")

    def get_next_invoice_number(self):
        """
            Get the next invoice number from the invoice number file.

            Args:
                None
            Returns:
                int: The next invoice number.
        """
        with open("invoice_number.txt", "r+") as f:
            number = int(f.read().strip())
            f.seek(0)
            f.write(str(number + 1))
        return number + 1


if __name__ == "__main__":
    app = InvoiceGeneratorApp()
    app.mainloop()

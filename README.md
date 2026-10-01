# Invoice Generator

## Table of Contents
[Overview](#overview)</br>
[Features](#features)</br>
[Requirements](#requirements)</br>
[Installation](#installation)</br>
[Usage](#usage)</br>
[File Structure](#file-structure)</br>
[License](#license)</br>
[Contact](#contact)</br>

## Overview

The Invoice Generator is a Python-based GUI app that allows users to create customizable,
professional invoices with ease for self-employed individuals.

_**Solely because I hate paying for QuickBooks.**_

## Features

- **Modern themed UI**: A responsive `ttk` interface with card-based sections, a sticky
  header (invoice number badge) and footer, plus a persistent dark/light theme toggle.
- **Company & Customer Information**: All contact fields — including company email and the
  customer's email, address, and city — are now editable directly in the app (previously
  config-only). An optional logo preview is shown when [Pillow](https://python-pillow.org/)
  is installed.
- **Inline Line Items**: Add, edit, and remove line items right in the main window with a
  per-row calendar date picker and a remove button — no separate window required.
- **Live Total**: The running total updates in real time in the footer as you type, and money
  fields are validated as you go.
- **Editable Invoice Number**: The header shows the next invoice number by default, but you can
  type any number to override it. Leave it blank to use the next number in sequence.
- **Date Selection**: Calendar widget for picking the invoice date, due date, or any line-item date.
- **Draft Management**: Save, load, and delete drafts from a Treeview-based drafts manager
  (double-click a draft to load it).
- **Default Values**: Predefined company and customer information to save time, see step 3 of [Installation](#installation).
- **Invoice Number Tracking**: Uses SQLite-backed persistent counters with one-time migration from `invoice_number.txt`.
- **A4 PDF Format**: PDFs are created in standard A4 ~~wagyu steak~~ PDF format.

## Requirements

- Python 3.11.2 or higher
- Tkinter
- tkcalendar
- ReportLab
- Pillow (optional — enables the in-app logo preview)

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/ProjectZuki/invoice-generator.git
   cd invoice-generator

2. Install Dependencies
```bash
pip install -r requirements.txt
```
3. Modify [config.txt file](SAMPLE_config.txt). </br>
_Note: Change the name from `SAMPLE_config.txt` &rarr; `config.txt`

4. Run
```bash
python invoicegen.py
```

## Usage
1. Launch the application using `python invoicegen.py`
2. Input company and client information (pre-loaded from `config.txt`, but fully editable in the UI).
3. Add line items:
    - Click `＋ Add Line` to add a row directly in the **Line Items** card, and `✕` to remove one.
    - Use the 📅 button on any row to pick a date. The footer total updates live as you type.
4. Optionally change the **Invoice #** in the header. It defaults to the next number in sequence;
   leave it blank to keep that default, or type a specific number to override it.
5. Use `Save Draft` to save in-progress invoice data and `Manage Drafts` to load or delete drafts
   (double-click a draft to load it).
6. After filling the required information, clicking `Generate Invoice` will generate an A4 PDF invoice
saved to the directory `invoices/`. The app stays open so you can issue more invoices.
7. The invoice will automatically open for viewing.

## File Structure

```
├── files/
│   ├── companyimage.png         # Default company logo image
│   └── signature.png            # Default signature image
├── invoicegen.py                # Main application script
├── invoice_counter.db           # SQLite storage for invoice counters and drafts (created at runtime)
├── invoice_number.txt           # Legacy counter file used for one-time migration
├── README.md                    # Project documentation
└── config.txt                   # Configuration file for default values
```

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact
For any questions or suggestions, feel free to contact me at [willie.alcaraz@gmail.com](mailto:willie.alcaraz@gmail.com?subject=GitHub%20Invoice%20Generator%20Repository%20Inquiry).
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

- **Company Information**: Input company name, logo, address, and details
- **Customer Information**: Client details such as name, address, and phone number.
- **Date Selection**: Utilizes calendar widget for date input (if different from default current date).
- **Line Items**: Add multiple line items with details for date, description, location, and rate.
- **Default Values**: Predefined company and customer information to save time, see step 4 of [Installation](#installation).
- **Customization**: Company log utilized is located in `files/companyimage.png`.
- **A4 PDF Format**: PDFs are created in standard A4 ~~wagyu steak~~ PDF format.

## Requirements

- Python 3.11.2 or higher
- Tkinter
- tkcalendar
- ReportLab

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
2. Input company and client information (using config.txt file). The information should be pre-loaded but open to modification.
3. Add line items:
    - To add line items, click `+ Add Line` button to add line items to the invoice. When finished, click `Generate Invoice`.
4. After filling the required information, clicking `Generate Invoice` will generate an A4 PDF invoice
saved to the directory `invoices/`
5. The invoice will automatically open for viewing.

## File Structure

```
├── files/
│   ├── companyimage.png         # Default company logo image
│   └── signature.png            # Default signature image
├── invoice_generator.py         # Main application script
├── invoice_number.txt           # Keeps track of the last invoice number
├── README.md                    # Project documentation
└── config.txt                   # Configuration file for default values
```

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact
For any questions or suggestions, feel free to contact me at [willie.alcaraz@gmail.com](mailto:willie.alcaraz@gmail.com?subject=GitHub%20Invoice%20Generator%20Repository%20Inquiry).
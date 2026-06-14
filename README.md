# ZEBRA: Barcode Label Designer & ZPL Printer Orchestrator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask Version](https://img.shields.io/badge/Flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)

`ZEBRA` is a professional, hardware-integrated web application and command-line automation toolkit designed to compose, preview, and print high-quality ZPL labels on Zebra industrial and desktop printers. Featuring a drag-and-drop WYSIWYG canvas editor, the system automatically translates visual elements (such as text, barcode parameters, QR codes, geometric borders, and uploaded images) directly into native ZPL (Zebra Programming Language) instruction streams.

---

## System Architecture

The application handles rendering, compilation, and hardware printing via the following pipeline:

```mermaid
graph TD
    Client[Browser WYSIWYG Editor] -->|1. JSON Elements Payload| Server[Flask API Server]
    Client -->|Optional: Rendered Canvas Image| Server
    
    subgraph Browser Frontend (static/index.html)
        Canvas[WYSIWYG Canvas]
        BarGen[JsBarcode / QR Code Generators]
    end
    
    subgraph Flask Backend (editor_app.py)
        Parser[JSON to ZPL Translator]
        ImgZPL[PIL Image-to-ZPL Bitonal Compiler]
        Win32[Win32 raw USB Write Handler]
    end
    
    subgraph Local Hardware
        USB[Zebra USB / Network Printer]
    end
    
    %% Flow mapping
    Canvas -->|Ajax POST /print| Parser
    BarGen -->|Embed Canvas Images| Canvas
    Parser -->|Generate ZPL Strings| Win32
    ImgZPL -->|Write Bitonal Hex Streams| Win32
    Win32 -->|Raw USB write via Kernel32.CreateFileW| USB
```

---

## File Structure

```
ZEBRA/
│
├── static/
│   └── index.html              # Drag-and-drop label designer UI (overhauled styling)
│
├── image/                      # Project static images and client logo branding
├── editor_app.py               # Flask backend with ZPL compilation and direct Win32 printing
├── print_stickers.py           # CLI automated printing pipeline from Excel spreadsheets
├── Etiquetas.xlsx              # Sample Excel datasheet defining label attributes
├── open_firewall.bat           # Firewall configurations for network-shared printers
├── requirements.txt            # Python application dependencies
└── README.md                   # This instruction manual
```

---

## Features

*   **WYSIWYG Interactive Editor**: Drag, drop, scale, duplicate, and align text, QR codes, barcode items, boxes, and lines on an adjustable dot-based canvas.
*   **Rotational Logic**: Full support for rotating the label layouts ($0^\circ$, $90^\circ$, $180^\circ$, $270^\circ$) with automatic ZPL dimension adjustments.
*   **Spreadsheet-to-Sticker CLI**: Batch process printing queues from Excel datasheets (`Etiquetas.xlsx`) using `print_stickers.py`.
*   **Vanity Barcodes**: Build custom stylized barcode designs (e.g., Computer, Mug, Laptop, and Book silhouettes) embedded with active scan signals.
*   **Direct Hardware Writing**: Employs Python `ctypes` bindings to directly write raw byte packets to the printer via the Windows kernel driver, bypassing spooler latency.

---

## Quick Start (Local Development)

### 1. Setup Environment
```bash
# Create Python Virtual Env
python -m venv .venv

# Activate Virtual Env (Windows)
.\.venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

### 2. Configure Zebra USB Path
Locate the USB device path for your Zebra printer on Windows (using Device Manager or USB tree viewer). In [editor_app.py](file:///c:/Users/CarlosAlbertoAcevesC/BOT/ZEBRA/editor_app.py), update the `ZEBRA_DEVICE_PATH` connection string:
```python
ZEBRA_DEVICE_PATH = r"\\?\USB#VID_0A5F&PID_0065#JAY247698#{28d78fad-5a12-11d1-ae5b-0000f803a8c2}"
```

### 3. Run the Web Designer
```bash
python editor_app.py
```
Open `http://localhost:5005` in your browser.

---

## Direct Batch CLI Printing (Excel)

To print labels in batches directly from an Excel spreadsheet without launching the web service:
1. Populate your label data inside [Etiquetas.xlsx](file:///c:/Users/CarlosAlbertoAcevesC/BOT/ZEBRA/Etiquetas.xlsx) (ensuring column fields match target tags).
2. Execute the CLI printing script:
   ```bash
   python print_stickers.py
   ```

---

## API References

### `POST /print`
Accepts a JSON list of layout elements, compiles it to ZPL, and prints it directly to the configured USB device.
*   **Payload Format**:
    ```json
    {
      "canvasWidth": 800,
      "canvasHeight": 1200,
      "rotate": 0,
      "elements": [
        { "type": "text", "x": 100, "y": 120, "text": "ASSET-1029", "fontSize": 45 },
        { "type": "barcode", "x": 100, "y": 200, "data": "10293847", "height": 80 }
      ]
    }
    ```

### `POST /print-bitmap`
Prints a pre-rendered base64 image (useful when sending pre-rasterized designs directly to ZPL graphic fields).
*   **Payload Format**:
    ```json
    {
      "width": 800,
      "height": 600,
      "image": "data:image/png;base64,iVBORw0KGgoAAA..."
    }
    ```

---

## Troubleshooting Printer Connectivity

> [!WARNING]
> Windows raw print handles (`CreateFileW`) require administrative or appropriate hardware execution context.
> - **Error: "Could not connect to Zebra printer"**: Ensure the printer is turned on, connected via USB, and the `ZEBRA_DEVICE_PATH` string exactly matches the active hardware device ID.
> - **Firewall Restrictions**: If serving the editor app across a local area network, run [open_firewall.bat](file:///c:/Users/CarlosAlbertoAcevesC/BOT/ZEBRA/open_firewall.bat) as Administrator to whitelist port `5005` for incoming connections.

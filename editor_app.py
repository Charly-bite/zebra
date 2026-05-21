import os
import ctypes
import ctypes.wintypes
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
import io
import base64

app = Flask(__name__, static_folder='static')
CORS(app)

ZEBRA_DEVICE_PATH = r"\\?\USB#VID_0A5F&PID_0065#JAY247698#{28d78fad-5a12-11d1-ae5b-0000f803a8c2}"
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = -1

class ZebraUSB:
    def __init__(self, device_path: str):
        self.device_path = device_path
        self.handle = None
        self.kernel32 = ctypes.windll.kernel32

    def open(self) -> bool:
        self.handle = self.kernel32.CreateFileW(
            self.device_path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None
        )
        return self.handle != INVALID_HANDLE_VALUE

    def write(self, data: bytes) -> bool:
        if not self.handle or self.handle == INVALID_HANDLE_VALUE: return False
        bytes_written = ctypes.wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(data)
        return self.kernel32.WriteFile(self.handle, buf, len(data), ctypes.byref(bytes_written), None)

    def close(self):
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

def image_to_zpl(base64_str, x, y, width=None, height=None):
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    
    try:
        image_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_data))
        
        if width and height:
            img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
        
        img = img.convert("1")
        
        width_px, height_px = img.size
        bytes_per_row = (width_px + 7) // 8
        total_bytes = bytes_per_row * height_px
        
        hex_data = ""
        for y_pos in range(height_px):
            row_bytes = bytearray(bytes_per_row)
            for x_pos in range(width_px):
                pixel = img.getpixel((x_pos, y_pos))
                if pixel == 0:  # Black pixel
                    byte_idx = x_pos // 8
                    bit_idx = 7 - (x_pos % 8)
                    row_bytes[byte_idx] |= (1 << bit_idx)
            
            hex_data += "".join(f"{b:02X}" for b in row_bytes) + "\n"
            
        return f"^FO{x},{y}^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS"
    except Exception as e:
        print("Image processing error:", e)
        return ""

def build_zpl(elements, canvas_width=1189, canvas_height=795):
    zpl = ["^XA", "^CI28", f"^PW{canvas_width}", f"^LL{canvas_height}"]
    for el in elements:
        x = int(el.get('x', 0))
        y = int(el.get('y', 0))
        el_type = el.get('type')
        if el_type == 'text':
            size = int(el.get('fontSize', 30))
            text = str(el.get('text', ''))
            zpl.append(f"^FO{x},{y}^A0N,{size},{size}^FD{text}^FS")
        elif el_type == 'barcode':
            data = str(el.get('data', ''))
            height = int(el.get('height', 100))
            zpl.append(f"^FO{x},{y}^BY3,3,{height}^BCN,{height},Y,N,N^FD{data}^FS")
        elif el_type == 'qrcode':
            data = str(el.get('data', ''))
            mag = int(el.get('size', 5))
            zpl.append(f"^FO{x},{y}^BQN,2,{mag}^FDQA,{data}^FS")
        elif el_type == 'box':
            w = int(el.get('width', 100))
            h = int(el.get('height', 100))
            t = int(el.get('thickness', 2))
            zpl.append(f"^FO{x},{y}^GB{w},{h},{t}^FS")
        elif el_type == 'image':
            base64_data = el.get('src', '')
            w = el.get('width')
            h = el.get('height')
            if base64_data:
                zpl_img = image_to_zpl(base64_data, x, y, w, h)
                if zpl_img:
                    zpl.append(zpl_img)
    zpl.append("^PQ1")
    zpl.append("^XZ")
    return "\n".join(zpl)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/print', methods=['POST'])
def print_label():
    data = request.json
    if not isinstance(data, dict) or 'elements' not in data:
        return jsonify({"success": False, "error": "Invalid payload format"}), 400
    
    elements = data.get('elements', [])
    canvas_w = int(data.get('canvasWidth', 1189))
    canvas_h = int(data.get('canvasHeight', 795))
    
    zpl = build_zpl(elements, canvas_w, canvas_h)
    print("Generating ZPL:\n", zpl)
    
    try:
        with ZebraUSB(ZEBRA_DEVICE_PATH) as printer:
            if not printer.handle or printer.handle == INVALID_HANDLE_VALUE:
                return jsonify({"success": False, "error": "Could not connect to Zebra printer (Check USB and Power)"}), 500
            
            if printer.write(zpl.encode("utf-8", errors="replace")):
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to write to printer"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Zebra Label Editor Server...")
    print("Open http://localhost:5000 in your browser.")
    app.run(host='0.0.0.0', port=5000)

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
        if not self.handle or self.handle == INVALID_HANDLE_VALUE:
            return False
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

def image_to_zpl(base64_str, x, y, width=None, height=None, rotate_angle=0):
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    
    try:
        image_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_data))
        
        if width and height:
            img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
        
        # Rotate image if needed (PIL rotate is counter-clockwise, so negate)
        if rotate_angle in (90, 180, 270):
            img = img.rotate(-rotate_angle, expand=True)
        
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

def get_element_dims(el):
    """Get approximate (width, height) of an element."""
    el_type = el.get('type')
    if el_type == 'text':
        h = int(el.get('fontSize', 30))
        w = int(h * len(str(el.get('text', ''))) * 0.6)
        return w, h
    elif el_type == 'barcode':
        return len(str(el.get('data', ''))) * 30, int(el.get('height', 100))
    elif el_type == 'qrcode':
        sz = int(el.get('size', 5)) * 20
        return sz, sz
    elif el_type == 'box':
        return int(el.get('width', 100)), int(el.get('height', 100))
    elif el_type == 'image':
        return int(el.get('width', 100)), int(el.get('height', 100))
    return 0, 0

def build_zpl(elements, canvas_width=1189, canvas_height=795, rotate_angle=0):
    # ZPL orientation codes: N=Normal(0°), R=90°CW, I=180°, B=270°CW(=90°CCW)
    orient_map = {0: 'N', 90: 'R', 180: 'I', 270: 'B'}
    orient = orient_map.get(rotate_angle, 'N')

    if rotate_angle in (90, 180, 270):
        new_elements = []
        for el in elements:
            el = dict(el)  # copy
            old_x = int(el.get('x', 0))
            old_y = int(el.get('y', 0))
            el_w, el_h = get_element_dims(el)

            if rotate_angle == 90:
                # 90° CW: (x, y) -> (canvas_h - y - el_h, x)
                el['x'] = canvas_height - old_y - el_h
                el['y'] = old_x
                # Swap box dimensions
                if el.get('type') == 'box':
                    el['width'], el['height'] = el.get('height', 100), el.get('width', 100)
            elif rotate_angle == 180:
                # 180°: (x, y) -> (canvas_w - x - el_w, canvas_h - y - el_h)
                el['x'] = canvas_width - old_x - el_w
                el['y'] = canvas_height - old_y - el_h
            elif rotate_angle == 270:
                # 270° CW (= 90° CCW): (x, y) -> (y, canvas_w - x - el_w)
                el['x'] = old_y
                el['y'] = canvas_width - old_x - el_w
                # Swap box dimensions
                if el.get('type') == 'box':
                    el['width'], el['height'] = el.get('height', 100), el.get('width', 100)

            new_elements.append(el)

        elements = new_elements
        # Swap canvas dimensions for 90° and 270°
        if rotate_angle in (90, 270):
            canvas_width, canvas_height = canvas_height, canvas_width

    zpl = ["^XA", "^CI28", f"^PW{canvas_width}", f"^LL{canvas_height}"]
    for el in elements:
        x = int(el.get('x', 0))
        y = int(el.get('y', 0))
        el_type = el.get('type')
        if el_type == 'text':
            size = int(el.get('fontSize', 30))
            text = str(el.get('text', ''))
            zpl.append(f"^FO{x},{y}^A0{orient},{size},{size}^FD{text}^FS")
        elif el_type == 'barcode':
            data = str(el.get('data', ''))
            height = int(el.get('height', 100))
            zpl.append(f"^FO{x},{y}^BY3,3,{height}^BC{orient},{height},Y,N,N^FD{data}^FS")
        elif el_type == 'qrcode':
            data = str(el.get('data', ''))
            mag = int(el.get('size', 5))
            zpl.append(f"^FO{x},{y}^BQ{orient},2,{mag}^FDQA,{data}^FS")
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
                zpl_img = image_to_zpl(base64_data, x, y, w, h, rotate_angle=rotate_angle)
                if zpl_img:
                    zpl.append(zpl_img)
    zpl.append("^PQ1")
    zpl.append("^XZ")
    return "\n".join(zpl)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/image/<path:filename>')
def serve_image(filename):
    """Serve files from the image directory."""
    return send_from_directory('image', filename)

@app.route('/print', methods=['POST'])
def print_label():
    data = request.json
    if not isinstance(data, dict) or 'elements' not in data:
        return jsonify({"success": False, "error": "Invalid payload format"}), 400
    
    elements = data.get('elements', [])
    canvas_w = int(data.get('canvasWidth', 1189))
    canvas_h = int(data.get('canvasHeight', 795))
    rotate_angle = int(data.get('rotate', 0))
    if rotate_angle not in (0, 90, 180, 270):
        rotate_angle = 0
    
    zpl = build_zpl(elements, canvas_w, canvas_h, rotate_angle=rotate_angle)
    print(f"Generating ZPL (rotate={rotate_angle}°):\n", zpl)
    
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

@app.route('/print-bitmap', methods=['POST'])
def print_bitmap():
    """Print a pre-rendered label image (used for rotated labels)."""
    data = request.json
    if not isinstance(data, dict) or 'image' not in data:
        return jsonify({"success": False, "error": "Missing image data"}), 400
    
    base64_data = data['image']
    width = int(data.get('width', 800))
    height = int(data.get('height', 600))
    
    print(f"Printing bitmap label ({width}x{height})...")
    
    # Convert the pre-rotated image to ZPL graphic field
    zpl_img = image_to_zpl(base64_data, 0, 0)  # No resize, no rotation - already done
    if not zpl_img:
        return jsonify({"success": False, "error": "Failed to process image"}), 500
    
    zpl = f"^XA\n^CI28\n^PW{width}\n^LL{height}\n{zpl_img}\n^PQ1\n^XZ"
    
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
    print("Open http://192.168.2.172:5005 in your browser.")
    app.run(host='0.0.0.0', port=5005)

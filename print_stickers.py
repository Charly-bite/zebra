# -*- coding: utf-8 -*-
import sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

"""
Zebra ZM400 Sticker Printer - Driver Bypass Script
===================================================
Reads equipment data from Etiquetas.xlsx and sends ZPL labels
directly to the Zebra ZM400-200dpi via USB, bypassing Windows drivers.

Usage:
    python print_stickers.py                  # Print ALL stickers
    python print_stickers.py --list           # List all labels (no printing)
    python print_stickers.py --rows 2 5 10    # Print specific rows only
    python print_stickers.py --range 2 10     # Print rows 2 through 10
    python print_stickers.py --test           # Print a single test label
    python print_stickers.py --dry-run        # Generate ZPL but don't send to printer
"""

import ctypes
import ctypes.wintypes
import argparse
import time
import openpyxl


# ─── USB Device Configuration ────────────────────────────────────────────────
# Zebra ZM400-200dpi ZPL connected via USB
ZEBRA_DEVICE_PATH = r"\\?\USB#VID_0A5F&PID_0065#JAY247698#{28d78fad-5a12-11d1-ae5b-0000f803a8c2}"

# Windows API constants
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = -1


# ─── Colors for terminal output ──────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"


# ─── USB Raw Communication ───────────────────────────────────────────────────
class ZebraUSB:
    """Direct USB communication with Zebra printer, no drivers needed."""

    def __init__(self, device_path: str):
        self.device_path = device_path
        self.handle = None
        self.kernel32 = ctypes.windll.kernel32

    def open(self) -> bool:
        """Open a raw file handle to the USB printer device."""
        self.handle = self.kernel32.CreateFileW(
            self.device_path,
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if self.handle == INVALID_HANDLE_VALUE:
            error_code = ctypes.GetLastError()
            print(f"{C.RED}[FAIL] Failed to open Zebra USB device (error {error_code}){C.RESET}")
            if error_code == 5:
                print(f"  {C.YELLOW}> Access denied. Try running as Administrator.{C.RESET}")
            elif error_code == 2:
                print(f"  {C.YELLOW}> Device not found. Is the Zebra powered on and connected?{C.RESET}")
            return False
        return True

    def write(self, data: bytes) -> bool:
        """Write raw bytes (ZPL) to the printer."""
        if self.handle is None or self.handle == INVALID_HANDLE_VALUE:
            print(f"{C.RED}[FAIL] Printer not connected{C.RESET}")
            return False

        bytes_written = ctypes.wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(data)
        success = self.kernel32.WriteFile(
            self.handle,
            buf,
            len(data),
            ctypes.byref(bytes_written),
            None,
        )
        if not success:
            error_code = ctypes.GetLastError()
            print(f"{C.RED}[FAIL] Write failed (error {error_code}){C.RESET}")
            return False
        return True

    def close(self):
        """Close the device handle."""
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


# ─── ZPL Label Generation ────────────────────────────────────────────────────

def clean(value) -> str:
    """Clean a cell value: strip leading underscores, handle None."""
    if value is None:
        return ""
    s = str(value).strip()
    # Remove leading underscores that are used as prefixes in the spreadsheet
    if s.startswith("_"):
        s = s[1:]
    return s


def generate_zpl_label(row_data: dict) -> str:
    """
    Generate a ZPL label for an equipment asset sticker.

    Label size: 151mm x 101mm at 200 dpi = 1189 x 795 dots
    """
    ubicacion = clean(row_data["ubicacion"])
    id_equipo = clean(row_data["id_equipo"])
    tipo      = clean(row_data["tipo"])
    marca     = clean(row_data["marca"])
    modelo    = clean(row_data["modelo"])
    serial    = clean(row_data["serial"])
    usuario   = clean(row_data["usuario"])
    area      = clean(row_data["area"])
    area_code = clean(row_data["area_code"])
    estado    = clean(row_data["estado"])

    # Build barcode data: location-areacode-id
    barcode_data = f"{ubicacion}-{area_code}-{id_equipo}"

    # Map type codes to readable names
    tipo_display = {
        "PC": "PC", "LTP": "LAPTOP", "IMP": "IMPRESORA",
        "MON": "MONITOR", "SRV": "SERVER",
    }.get(tipo, tipo)

    zpl = f"""^XA
^CI28
^PW1189
^LL795
^FO40,60^GB1109,0,4^FS
^FO40,75^A0N,50,50^FD ETIQUETA DE ACTIVO^FS
^FO40,140^GB1109,0,2^FS
^FO40,165^A0N,28,28^FDUbicacion:^FS
^FO260,165^A0N,32,32^FD{ubicacion}^FS
^FO600,165^A0N,28,28^FDID:^FS
^FO680,165^A0N,32,32^FD{id_equipo}^FS
^FO40,215^A0N,28,28^FDTipo:^FS
^FO260,215^A0N,32,32^FD{tipo_display}^FS
^FO600,215^A0N,28,28^FDMarca:^FS
^FO700,215^A0N,32,32^FD{marca[:25]}^FS
^FO40,265^A0N,28,28^FDModelo:^FS
^FO260,265^A0N,32,32^FD{modelo[:40]}^FS
^FO40,315^A0N,28,28^FDSerie:^FS
^FO260,315^A0N,32,32^FD{serial[:35]}^FS
^FO40,365^A0N,28,28^FDEstado:^FS
^FO260,365^A0N,32,32^FD{estado}^FS
^FO40,410^GB1109,0,2^FS
^FO40,435^A0N,28,28^FDUsuario:^FS
^FO200,435^A0N,32,32^FD{usuario[:45]}^FS
^FO40,485^A0N,28,28^FDArea:^FS
^FO200,485^A0N,32,32^FD{area} ({area_code})^FS
^FO40,530^GB1109,0,2^FS
^FO40,555^BY2,3,100^BCN,100,Y,N,N^FD{barcode_data}^FS
^FO40,685^A0N,22,22^FD{barcode_data}^FS
^FO40,720^GB1109,0,4^FS
^PQ1
^XZ
"""
    return zpl


def generate_test_zpl() -> str:
    """Generate a simple test label to verify printer connectivity."""
    return """^XA
^CI28
^PW1189
^LL795
^FO40,25^GB1109,0,4^FS
^FO40,50^A0N,60,60^FD TEST LABEL^FS
^FO40,130^GB1109,0,2^FS
^FO40,160^A0N,36,36^FDZebra ZM400 - Direct USB^FS
^FO40,210^A0N,36,36^FDDriver Bypass: OK^FS
^FO40,270^A0N,30,30^FDLabel size: 151mm x 101mm^FS
^FO40,310^A0N,30,30^FDIf you can read this,^FS
^FO40,350^A0N,30,30^FDthe connection works!^FS
^FO40,420^BY3,3,100^BCN,100,Y,N,N^FDTEST-OK^FS
^FO40,560^GB1109,0,4^FS
^PQ1
^XZ
"""


# ─── Excel Data Reader ───────────────────────────────────────────────────────

def read_equipment_data(filepath: str) -> list[dict]:
    """Read all valid equipment rows from the Excel file."""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    records = []

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        vals = [cell.value for cell in row]

        # Skip empty rows or rows without equipment
        if not vals[0] or not vals[1]:
            continue
        if vals[3] and "NO HAY" in str(vals[3]).upper():
            continue

        records.append({
            "row_num":   row[0].row,
            "ubicacion": vals[0],
            "id_equipo": vals[1],
            "tipo":      vals[2],
            "marca":     vals[3],
            "modelo":    vals[4],
            "serial":    vals[5],
            "usuario":   vals[6],
            "username":  vals[7],
            "area":      vals[8],
            "area_code": vals[9],
            "estado":    vals[10],
        })

    wb.close()
    return records


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Print asset stickers on Zebra ZM400 via direct USB (no drivers)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python print_stickers.py --list           List all labels
  python print_stickers.py --test           Print a test label
  python print_stickers.py --rows 2 5 10    Print specific rows
  python print_stickers.py --range 2 10     Print a range of rows
  python print_stickers.py --dry-run        Preview ZPL without printing
  python print_stickers.py                  Print ALL stickers
        """,
    )
    parser.add_argument("--list", action="store_true", help="List all equipment labels without printing")
    parser.add_argument("--test", action="store_true", help="Print a single test label")
    parser.add_argument("--rows", nargs="+", type=int, help="Print only these specific Excel row numbers")
    parser.add_argument("--range", nargs=2, type=int, metavar=("FROM", "TO"), help="Print rows in this range (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Generate ZPL but don't send to printer")
    parser.add_argument("--file", default="Etiquetas.xlsx", help="Path to Excel file (default: Etiquetas.xlsx)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between labels (default: 1.0)")
    args = parser.parse_args()

    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.file)

    print(f"\n{C.BOLD}{'=' * 55}{C.RESET}")
    print(f"{C.BOLD}  [PRINTER] Zebra ZM400 - Direct USB Sticker Printer{C.RESET}")
    print(f"{C.BOLD}{'=' * 55}{C.RESET}\n")

    # ── Test mode ─────────────────────────────────────────
    if args.test:
        print(f"{C.CYAN}> Sending test label...{C.RESET}")
        zpl = generate_test_zpl()

        if args.dry_run:
            print(f"\n{C.DIM}{zpl}{C.RESET}")
            print(f"{C.GREEN}[OK] Dry run complete (no data sent){C.RESET}")
            return

        with ZebraUSB(ZEBRA_DEVICE_PATH) as printer:
            if printer.handle and printer.handle != INVALID_HANDLE_VALUE:
                if printer.write(zpl.encode("utf-8", errors="replace")):
                    print(f"{C.GREEN}[OK] Test label sent successfully!{C.RESET}")
                else:
                    print(f"{C.RED}[FAIL] Failed to send test label{C.RESET}")
            else:
                sys.exit(1)
        return

    # ── Read data ─────────────────────────────────────────
    if not os.path.exists(excel_path):
        print(f"{C.RED}[FAIL] File not found: {excel_path}{C.RESET}")
        sys.exit(1)

    print(f"{C.DIM}  Reading: {os.path.basename(excel_path)}{C.RESET}")
    records = read_equipment_data(excel_path)
    print(f"{C.GREEN}  [OK] Found {len(records)} equipment records{C.RESET}\n")

    if not records:
        print(f"{C.YELLOW}  No valid records to print.{C.RESET}")
        return

    # ── Filter by rows if specified ───────────────────────
    if args.rows:
        records = [r for r in records if r["row_num"] in args.rows]
        print(f"{C.CYAN}  > Filtered to {len(records)} rows: {args.rows}{C.RESET}\n")
    elif args.range:
        from_row, to_row = args.range
        records = [r for r in records if from_row <= r["row_num"] <= to_row]
        print(f"{C.CYAN}  > Filtered to {len(records)} rows: {from_row}-{to_row}{C.RESET}\n")

    # ── List mode ─────────────────────────────────────────
    if args.list:
        print(f"  {'Row':<5} {'ID':<6} {'Type':<5} {'Brand':<12} {'User':<30} {'Area':<15}")
        print(f"  {'-' * 5} {'-' * 6} {'-' * 5} {'-' * 12} {'-' * 30} {'-' * 15}")
        for r in records:
            row_n = r["row_num"]
            id_eq = clean(r["id_equipo"])
            tipo  = clean(r["tipo"])
            marca = clean(r["marca"])
            user  = clean(r["usuario"])
            area  = clean(r["area"])
            print(f"  {row_n:<5} {id_eq:<6} {tipo:<5} {marca:<12} {user:<30} {area:<15}")
        print(f"\n  {C.DIM}Total: {len(records)} stickers{C.RESET}\n")
        return

    # ── Print mode ────────────────────────────────────────
    print(f"  {C.YELLOW}[!] About to print {len(records)} sticker(s){C.RESET}")
    print(f"  {C.DIM}Press Enter to continue, or Ctrl+C to cancel...{C.RESET}", end="")

    try:
        input()
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}  Cancelled.{C.RESET}")
        return

    if args.dry_run:
        for i, r in enumerate(records, 1):
            zpl = generate_zpl_label(r)
            id_eq = clean(r["id_equipo"])
            user  = clean(r["usuario"])
            print(f"\n{C.CYAN}-- Label {i}/{len(records)}: ID {id_eq} - {user} --{C.RESET}")
            print(f"{C.DIM}{zpl}{C.RESET}")
        print(f"\n{C.GREEN}[OK] Dry run complete - {len(records)} labels generated (nothing sent){C.RESET}")
        return

    # ── Send to printer ───────────────────────────────────
    with ZebraUSB(ZEBRA_DEVICE_PATH) as printer:
        if not printer.handle or printer.handle == INVALID_HANDLE_VALUE:
            sys.exit(1)

        print(f"  {C.GREEN}[OK] Connected to Zebra ZM400{C.RESET}\n")

        success_count = 0
        fail_count = 0

        for i, r in enumerate(records, 1):
            id_eq = clean(r["id_equipo"])
            user  = clean(r["usuario"])
            zpl = generate_zpl_label(r)

            print(f"  [{i:>3}/{len(records)}] ID {id_eq:<6} {user:<30} ", end="", flush=True)

            if printer.write(zpl.encode("utf-8", errors="replace")):
                print(f"{C.GREEN}[OK]{C.RESET}")
                success_count += 1
            else:
                print(f"{C.RED}[FAIL]{C.RESET}")
                fail_count += 1

            # Small delay between labels to avoid overwhelming the printer buffer
            if i < len(records):
                time.sleep(args.delay)

        print(f"\n{'=' * 55}")
        print(f"  {C.GREEN}[OK] Done: {success_count} printed{C.RESET}", end="")
        if fail_count:
            print(f", {C.RED}{fail_count} failed{C.RESET}")
        else:
            print()
        print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()

# PartsBuilderV2.py
# Version: v1.9.61 – Fix MID List Column Order
# Author: Assistant
# Date: 2025-12-14
# --------------------------------------------------------------
#  • If vendor_name missing → use MID → lookup ven_name
#  • First Cust. Ref. & File No. in GUI
#  • Export Sigma Upload unchanged
#  • Professional modern GUI with enhanced styling
# --------------------------------------------------------------

import sqlite3
import pandas as pd
import os
import threading
import time
import subprocess
import gc
from datetime import datetime
from tkinter import Tk, Button, Label, filedialog, messagebox, ttk, simpledialog
from tkinter import Scrollbar, Text

# Optional: pyperclip
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DB_FILE   = r'C:\Users\hpayne\Documents\DevHouston\PartsBuilder\Resources\DB\sigma.db'
MID_XLSX  = r'C:\Users\hpayne\Documents\DevHouston\PartsBuilder\Resources\SigmaMID.xlsx'

# Global for output DataFrame
OUTPUT_DF = None

# GUI globals
root = None
output_tree = None
log_text = None

# ----------------------------------------------------------------------
# Database initialisation
# ----------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS chp_entry (
        customer_id TEXT, vr_num TEXT, comm_inv_no TEXT, entry_no TEXT,
        product_no TEXT PRIMARY KEY, coo TEXT, mid TEXT, supplier TEXT,
        port_of_entry TEXT, port_of_entry_name TEXT, release_date TEXT,
        update_tariff_no TEXT, first_cust_ref TEXT, file_no TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS sigma_parts (
        product_no TEXT PRIMARY KEY, mid TEXT, vendor_name TEXT,
        final_hts TEXT, coo TEXT, sec_232_steel TEXT, sec_232_aluminum TEXT,
        sec_232_copper TEXT, sec_232_auto_parts TEXT, sec_232_wood TEXT,
        date_added TEXT, first_cust_ref TEXT, file_no TEXT, customer_id TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS sigma_mid_list (
        ven_mid TEXT PRIMARY KEY, ven_name TEXT)''')

    c.execute('DROP TABLE IF EXISTS debug_log')
    c.execute('''CREATE TABLE debug_log (
        log_type TEXT, product_no TEXT, mid TEXT, details TEXT,
        timestamp TEXT DEFAULT (datetime('now')))''')

    conn.commit()
    conn.close()

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
def log(msg_type, product_no='', mid='', details=''):
    timestamp = datetime.now().strftime("%H:%M:%S")
    msg = f"[{timestamp}] [{msg_type}] {product_no} | {details}"
    print(msg)

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO debug_log (log_type, product_no, mid, details) VALUES (?,?,?,?)",
            (msg_type, product_no, mid, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[LOG ERROR] {e}")

    if log_text:
        log_text.insert("end", msg + "\n")
        log_text.see("end")

    if root and hasattr(root, 'set_status'):
        root.set_status(f"{product_no} | {details[:60]}...")

# ----------------------------------------------------------------------
# Thread helper with cursor
# ----------------------------------------------------------------------
def run_in_thread(target, args=(), on_done=None):
    def wrapper():
        try:
            root.config(cursor="wait")
            root.update_idletasks()
            target(*args)
        except Exception as e:
            log("ERROR", "", "", f"Thread crash: {e}")
            messagebox.showerror("Error", f"Operation failed:\n{e}")
        finally:
            root.config(cursor="")
            root.update_idletasks()
            if on_done:
                root.after(0, on_done)
    threading.Thread(target=wrapper, daemon=True).start()

# ----------------------------------------------------------------------
# 1. Import CHP Entry Report – Any CSV Format
# ----------------------------------------------------------------------
def import_chp():
    def job():
        path = filedialog.askopenfilename(
            title="Select CHP Entry Report CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not path: return

        try:
            df = pd.read_csv(path)
            log("INFO", "", "", f"CHP CSV loaded: {len(df)} rows from {os.path.basename(path)}")

            col_map = {}
            for col in df.columns:
                c = col.strip()
                if c == 'Part Number':
                    col_map['product_no'] = col
                elif c == 'Manufacturer':
                    col_map['mid'] = col
                elif c == 'C/O':
                    col_map['coo'] = col
                elif c == 'Tariff No':
                    col_map['update_tariff_no'] = col
                elif c == 'First Cust. Ref.':
                    col_map['first_cust_ref'] = col
                elif c == 'File No.':
                    col_map['file_no'] = col
                elif c == 'Customer ID' or c == 'Cust ID' or c == 'CustID':
                    col_map['customer_id'] = col

            missing = [k for k in ['product_no', 'mid', 'coo', 'update_tariff_no'] if k not in col_map]
            if missing:
                messagebox.showerror("Error", f"Missing required columns in CSV file:\n{missing}\n\nFound columns: {list(df.columns)}")
                log("ERROR", "", "", f"Missing CHP columns: {missing}")
                return

            df = df.rename(columns={
                col_map['product_no']: 'product_no',
                col_map['mid']: 'mid',
                col_map['coo']: 'coo',
                col_map['update_tariff_no']: 'update_tariff_no',
                col_map.get('first_cust_ref', ''): 'first_cust_ref',
                col_map.get('file_no', ''): 'file_no',
                col_map.get('customer_id', ''): 'customer_id'
            })

            for col in ['product_no', 'mid', 'coo', 'update_tariff_no', 'first_cust_ref', 'file_no', 'customer_id']:
                if col not in df.columns:
                    df[col] = ''

            df = df[['product_no', 'mid', 'coo', 'update_tariff_no', 'first_cust_ref', 'file_no', 'customer_id']].drop_duplicates(subset='product_no')
            before = len(df)
            df = df[df['product_no'].notna() & (df['product_no'].astype(str).str.strip() != '')]
            after = len(df)
            if before != after:
                log("WARN", "", "", f"Skipped {before - after} rows with empty product_no")

            conn = sqlite3.connect(DB_FILE)
            df.to_sql('chp_entry', conn, if_exists='replace', index=False)
            conn.close()

            log("INFO", "", "", f"CHP imported: {len(df)} unique parts")
            messagebox.showinfo("Success", f"CHP imported: {len(df)} parts")
        except Exception as e:
            log("ERROR", "", "", f"CHP import failed: {e}")
            messagebox.showerror("Error", f"Import failed:\n{e}")

    run_in_thread(job)

# ----------------------------------------------------------------------
# 2. Import Sigma Parts – YOUR EXACT FORMAT
# ----------------------------------------------------------------------
def import_sigma_parts():
    # Prompt for client code before opening file dialog
    client_code = simpledialog.askstring("Client Code", "Enter Client Code:", parent=root)
    if not client_code:
        messagebox.showwarning("Cancelled", "Import cancelled - no client code provided.")
        return
    client_code = client_code.strip().upper()
    
    def job():
        path = filedialog.askopenfilename(title="Select Sigma Parts List", filetypes=[("Excel Files","*.xls *.xlsx")])
        if not path: return

        try:
            df = pd.read_excel(path)
            log("INFO", "", "", f"Sigma Parts loaded: {len(df)} rows for client {client_code}")

            col_map = {}
            for col in df.columns:
                c = col.strip().replace('%', '').replace('_', ' ').replace('-', ' ').upper()
                if c.replace(' ', '') == 'ITEM#':
                    col_map['product_no'] = col
                elif c == 'MID':
                    col_map['mid'] = col
                elif 'VENDOR' in c:
                    col_map['vendor_name'] = col
                elif 'FINAL HTS' in c:
                    col_map['final_hts'] = col
                elif c == 'COO':
                    col_map['coo'] = col
                elif 'SEC 232' in c and 'STEEL' in c:
                    col_map['sec_232_steel'] = col
                elif 'SEC 232' in c and ('ALUMINUM' in c or 'ALUM' in c):
                    col_map['sec_232_aluminum'] = col
                elif 'SEC 232' in c and 'COPPER' in c:
                    col_map['sec_232_copper'] = col
                elif 'SEC 232' in c and 'AUTO PARTS' in c:
                    col_map['sec_232_auto_parts'] = col
                elif 'SEC 232' in c and 'WOOD' in c:
                    col_map['sec_232_wood'] = col

            missing = [k for k in ['product_no', 'mid', 'vendor_name', 'final_hts', 'coo'] if k not in col_map]
            if missing:
                messagebox.showerror("Error", f"Missing columns in Sigma Parts file:\n{missing}")
                log("ERROR", "", "", f"Missing Sigma Parts columns: {missing}")
                return

            df = df.rename(columns={
                col_map['product_no']: 'product_no',
                col_map['mid']: 'mid',
                col_map['vendor_name']: 'vendor_name',
                col_map['final_hts']: 'final_hts',
                col_map['coo']: 'coo',
                col_map.get('sec_232_steel', ''): 'sec_232_steel',
                col_map.get('sec_232_aluminum', ''): 'sec_232_aluminum',
                col_map.get('sec_232_copper', ''): 'sec_232_copper',
                col_map.get('sec_232_auto_parts', ''): 'sec_232_auto_parts',
                col_map.get('sec_232_wood', ''): 'sec_232_wood'
            })

            for col in ['product_no', 'mid', 'vendor_name', 'final_hts', 'coo', 'sec_232_steel', 'sec_232_aluminum', 'sec_232_copper', 'sec_232_auto_parts', 'sec_232_wood']:
                if col not in df.columns:
                    df[col] = ''

            if 'date_added' not in df.columns:
                df['date_added'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

            # Add client code to customer_id field
            df['customer_id'] = client_code

            # Initialize other required fields
            if 'first_cust_ref' not in df.columns:
                df['first_cust_ref'] = ''
            if 'file_no' not in df.columns:
                df['file_no'] = ''

            df = df[['product_no', 'mid', 'vendor_name', 'final_hts', 'coo', 'sec_232_steel', 'sec_232_aluminum', 'sec_232_copper', 'sec_232_auto_parts', 'sec_232_wood', 'date_added', 'first_cust_ref', 'file_no', 'customer_id']].drop_duplicates(subset='product_no')

            conn = sqlite3.connect(DB_FILE)
            df.to_sql('sigma_parts', conn, if_exists='replace', index=False)
            conn.close()

            log("INFO", "", "", f"Sigma parts imported: {len(df)} unique parts for client {client_code}")
            messagebox.showinfo("Success", f"Sigma parts imported: {len(df)} parts\nClient Code: {client_code}")
        except Exception as e:
            log("ERROR", "", "", f"Sigma parts import failed: {e}")
            messagebox.showerror("Error", f"Import failed:\n{e}")

    run_in_thread(job)

# ----------------------------------------------------------------------
# 3. Import MID List
# ----------------------------------------------------------------------
def import_mid_list():
    def job():
        if not os.path.isfile(MID_XLSX):
            messagebox.showerror("Error", f"MID file not found:\n{MID_XLSX}")
            return
        # Read columns: 0=MANUFACTURER NAME, 1=MID, 2=CUSTOMER ID (optional)
        df = pd.read_excel(MID_XLSX, header=None, usecols=[0,1])
        # Column 0 is vendor name, Column 1 is MID
        df.columns = ['ven_name', 'ven_mid']
        df['ven_mid'] = df['ven_mid'].astype(str).str.strip().str.upper()
        df['ven_name'] = df['ven_name'].astype(str).str.strip()
        # Filter out rows where MID is empty
        df = df[df['ven_mid'].str.len() > 0]
        # Filter out rows where vendor name is empty
        df = df[df['ven_name'].str.len() > 0]

        log("INFO", "", "", f"MID list loaded: {len(df)} vendor/MID pairs")

        conn = sqlite3.connect(DB_FILE)
        df.to_sql('sigma_mid_list', conn, if_exists='replace', index=False)
        conn.close()
        log("INFO", "", "", f"MID list imported: {len(df)} records")
        messagebox.showinfo("Success", f"MID list imported: {len(df)} records")
    run_in_thread(job)

# ----------------------------------------------------------------------
# 4. Process & Export – VENDOR NAME FROM MID LIST
# ----------------------------------------------------------------------
def process_and_export():
    def job():
        global OUTPUT_DF
        log("INFO", "", "", "Starting process...")
        conn = sqlite3.connect(DB_FILE)
        chp = pd.read_sql_query("SELECT * FROM chp_entry", conn)
        parts = pd.read_sql_query("SELECT * FROM sigma_parts", conn)
        mid_map = pd.read_sql_query("SELECT * FROM sigma_mid_list", conn)
        conn.close()

        log("INFO", "", "", f"CHP loaded: {len(chp)} rows")
        log("INFO", "", "", f"Sigma Parts loaded: {len(parts)} rows")

        added = mid_updated = vendor_updated = skipped = 0

        # --- 1. RENAME COLUMN ---
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("ALTER TABLE sigma_parts RENAME COLUMN last_purchased_vendor_name TO vendor_name")
            log("INFO", "", "", "Column renamed: last_purchased_vendor_name to vendor_name")
        except sqlite3.OperationalError:
            pass
        conn.close()

        # --- 2. PROCESS CHP: ADD NEW PARTS WITH REF & FILE NO ---
        for idx, r in chp.iterrows():
            pn_raw = r.get('product_no')
            if pd.isna(pn_raw) or str(pn_raw).strip() == '':
                skipped += 1
                continue

            pn = str(pn_raw).strip()
            chp_mid = str(r.get('mid', '')).strip().upper()
            chp_coo = str(r.get('coo', '')).strip()
            chp_hts = str(r.get('update_tariff_no', '')).strip()
            chp_vendor = str(r.get('supplier', '')).strip()
            first_cust_ref = str(r.get('first_cust_ref', '')).strip()
            file_no = str(r.get('file_no', '')).strip()
            customer_id = str(r.get('customer_id', '')).strip()

            if pn in parts['product_no'].values:
                log("INFO", pn, "", f"Part exists in Sigma – keeping Sigma data")
                continue

            new = {
                'product_no': pn,
                'mid': chp_mid,
                'vendor_name': chp_vendor,
                'final_hts': chp_hts,
                'coo': chp_coo,
                'sec_232_steel': '',
                'sec_232_aluminum': '',
                'sec_232_copper': '',
                'sec_232_auto_parts': '',
                'sec_232_wood': '',
                'date_added': datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                'first_cust_ref': first_cust_ref,
                'file_no': file_no,
                'customer_id': customer_id
            }
            parts = pd.concat([parts, pd.DataFrame([new])], ignore_index=True)
            added += 1
            log("INFO", pn, chp_mid, f"Added new part from CHP")

        # --- 3. SAVE FINAL DATA ---
        conn = sqlite3.connect(DB_FILE)
        parts.to_sql('sigma_parts', conn, if_exists='replace', index=False)
        conn.close()

        # --- 4. UPDATE VENDOR NAME FROM MID LIST ---
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            UPDATE sigma_parts
            SET vendor_name = (
                SELECT ven_name FROM sigma_mid_list
                WHERE UPPER(TRIM(sigma_mid_list.ven_mid)) = UPPER(TRIM(sigma_parts.mid))
            )
            WHERE (vendor_name IS NULL OR vendor_name = '')
              AND (mid IS NOT NULL AND mid != '')
        """)
        vendor_updated = c.rowcount
        conn.commit()
        conn.close()
        if vendor_updated > 0:
            log("INFO", "", "", f"Updated {vendor_updated} vendor names from MID list")

        # --- 5. FINAL MID LOOKUP FOR ALL PARTS ---
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # First, check how many records have missing MID
        c.execute("SELECT COUNT(*) FROM sigma_parts WHERE mid IS NULL OR mid = ''")
        missing_mid_count = c.fetchone()[0]
        log("INFO", "", "", f"Found {missing_mid_count} parts with missing MID")

        # Update MID from vendor name lookup
        c.execute("""
            UPDATE sigma_parts
            SET mid = (
                SELECT ven_mid FROM sigma_mid_list
                WHERE UPPER(TRIM(sigma_mid_list.ven_name)) = UPPER(TRIM(sigma_parts.vendor_name))
            )
            WHERE (mid IS NULL OR mid = '')
              AND (vendor_name IS NOT NULL AND vendor_name != '')
              AND EXISTS (
                  SELECT 1 FROM sigma_mid_list
                  WHERE UPPER(TRIM(sigma_mid_list.ven_name)) = UPPER(TRIM(sigma_parts.vendor_name))
              )
        """)
        mid_updated = c.rowcount
        conn.commit()

        # Check how many still have missing MID after update
        c.execute("SELECT COUNT(*) FROM sigma_parts WHERE mid IS NULL OR mid = ''")
        still_missing = c.fetchone()[0]

        conn.close()

        # Reload updated data
        conn = sqlite3.connect(DB_FILE)
        parts = pd.read_sql_query("SELECT * FROM sigma_parts", conn)
        conn.close()

        if mid_updated > 0:
            log("INFO", "", "", f"Populated {mid_updated} MIDs from vendor_name")
        if still_missing > 0:
            log("WARN", "", "", f"{still_missing} parts still have missing MID after lookup")
            # Log which vendor names don't have MID matches
            conn = sqlite3.connect(DB_FILE)
            unmatched = pd.read_sql_query("""
                SELECT DISTINCT vendor_name, COUNT(*) as count
                FROM sigma_parts
                WHERE (mid IS NULL OR mid = '')
                  AND (vendor_name IS NOT NULL AND vendor_name != '')
                GROUP BY vendor_name
                LIMIT 10
            """, conn)
            conn.close()
            if len(unmatched) > 0:
                log("WARN", "", "", f"Vendor names without MID match: {', '.join(unmatched['vendor_name'].tolist())}")

        if skipped > 0:
            log("WARN", "", "", f"Skipped {skipped} CHP rows with empty product_no")

        OUTPUT_DF = parts.copy()
        export_report_with_cleanup(parts)
        root.after(0, lambda: refresh_output_tab())
        root.after(0, lambda: messagebox.showinfo("Done", f"Added: {added}\nMID Populated: {mid_updated}\nVendor Updated: {vendor_updated}\nSkipped: {skipped}"))
        log("INFO", "", "", f"Process complete – {added} added, {mid_updated} MIDs, {vendor_updated} vendors updated, {skipped} skipped.")
    run_in_thread(job)

def export_report_with_cleanup(df):
    try:
        # Ensure customer_id column exists
        if 'customer_id' not in df.columns:
            df['customer_id'] = ''
        out = df[['product_no','mid','vendor_name','final_hts',
                  'coo','sec_232_steel','sec_232_aluminum','sec_232_copper',
                  'sec_232_auto_parts','sec_232_wood','date_added',
                  'first_cust_ref','file_no','customer_id']].copy()
        out.columns = ['Product No','MID','Last purchase vendor name','FINAL HTS',
                       'COO','SEC 232 STEEL','SEC 232 ALUMINUM','SEC 232 COPPER',
                       'SEC 232 AUTO PARTS','SEC 232 WOOD','Date Added',
                       'First Cust. Ref.','File No.','Customer ID']
        file_path = os.path.join(r'C:\Users\hpayne\Documents\DevHouston\PartsBuilder',
                     f"SIGMA_PARTS_BUILDER_{datetime.now():%m-%d-%Y}.xls")
        out.to_excel(file_path, index=False, engine='openpyxl')
        log("INFO","","",f"Exported: {file_path}")
    except Exception as e:
        log("ERROR","","",f"Export failed: {e}")

# ----------------------------------------------------------------------
# 5. EXPORT TO SIGMA UPLOAD FORMAT (A, I, J, L, Q, AA, AB) – UNCHANGED
# ----------------------------------------------------------------------
def export_sigma_upload():
    if OUTPUT_DF is None:
        messagebox.showinfo("Info", "Run Process first.")
        return

    path = filedialog.asksaveasfilename(
        title="Save Sigma_Parts_Upload.xlsx",
        defaultextension=".xlsx",
        filetypes=[("Excel Files", "*.xlsx")],
        initialdir=r'C:\Users\hpayne\Documents\DevHouston\PartsBuilder'
    )
    if not path:
        return

    try:
        headers = [
            "Product No", "", "", "", "", "", "", "", "MID", "Last purchase vendor name",
            "", "FINAL HTS", "", "", "", "", "COO", "", "", "", "", "", "", "", "", "",
            "SEC 232 STEEL", "SEC 232 ALUMINUM", "SEC 232 COPPER", "SEC 232 AUTO PARTS", "SEC 232 WOOD"
        ]

        df = pd.DataFrame(columns=range(1, 32), index=OUTPUT_DF.index)
        df[1] = OUTPUT_DF['product_no']
        df[9] = OUTPUT_DF['mid']
        df[10] = OUTPUT_DF['vendor_name']
        df[12] = OUTPUT_DF['final_hts']
        df[17] = OUTPUT_DF['coo']
        df[27] = OUTPUT_DF['sec_232_steel']
        df[28] = OUTPUT_DF['sec_232_aluminum']
        df[29] = OUTPUT_DF['sec_232_copper']
        df[30] = OUTPUT_DF['sec_232_auto_parts']
        df[31] = OUTPUT_DF['sec_232_wood']

        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            header_df = pd.DataFrame([headers])
            header_df.to_excel(writer, index=False, header=False, startrow=0)
            df.to_excel(writer, index=False, header=False, startrow=1)

        messagebox.showinfo("Success", f"Sigma Upload exported:\n{path}")
        log("INFO","","",f"Sigma upload exported: {path}")
    except Exception as e:
        log("ERROR","","",f"Export failed: {e}")
        messagebox.showerror("Error", f"Export failed:\n{e}")

# ----------------------------------------------------------------------
# Apply Professional Theme
# ----------------------------------------------------------------------
def apply_professional_theme(root):
    """Apply modern professional styling to the application"""
    style = ttk.Style()

    # Configure overall theme - use clam or fallback to default
    try:
        style.theme_use('clam')
    except Exception:
        try:
            style.theme_use('alt')
        except Exception:
            pass  # Use default theme

    # Color scheme - Professional blue/grey palette
    colors = {
        'primary': '#2C3E50',      # Dark blue-grey
        'secondary': '#34495E',    # Medium blue-grey
        'accent': '#3498DB',       # Bright blue
        'success': '#27AE60',      # Green
        'background': '#ECF0F1',   # Light grey
        'surface': '#FFFFFF',      # White
        'text': '#2C3E50',         # Dark text
        'text_light': '#7F8C8D'    # Light text
    }

    # Configure Notebook (tabs)
    style.configure('TNotebook', background=colors['background'], borderwidth=0)
    style.configure('TNotebook.Tab',
                    background=colors['secondary'],
                    foreground='white',
                    padding=[15, 8],
                    font=('Segoe UI', 9, 'bold'))
    style.map('TNotebook.Tab',
              background=[('selected', colors['primary'])],
              foreground=[('selected', 'white')],
              expand=[('selected', [1, 1, 1, 0])])

    # Configure Frames
    style.configure('TFrame', background=colors['background'])
    style.configure('Card.TFrame', background=colors['surface'], relief='flat')

    # Configure Labels
    style.configure('TLabel', background=colors['background'], foreground=colors['text'], font=('Segoe UI', 9))
    style.configure('Title.TLabel', font=('Segoe UI', 13, 'bold'), foreground=colors['primary'], background=colors['background'])
    style.configure('Subtitle.TLabel', font=('Segoe UI', 10, 'bold'), foreground=colors['secondary'], background=colors['background'])

    # Configure LabelFrames
    style.configure('TLabelframe', background=colors['background'], borderwidth=2, relief='groove')
    style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'), foreground=colors['primary'], background=colors['background'])

    # Configure Treeview
    style.configure('Treeview',
                    background=colors['surface'],
                    foreground=colors['text'],
                    fieldbackground=colors['surface'],
                    font=('Segoe UI', 9),
                    rowheight=22)
    style.configure('Treeview.Heading',
                    background=colors['primary'],
                    foreground='white',
                    font=('Segoe UI', 9, 'bold'),
                    relief='flat')
    style.map('Treeview.Heading',
              background=[('active', colors['accent'])])
    style.map('Treeview',
              background=[('selected', colors['accent'])],
              foreground=[('selected', 'white')])

    # Configure Buttons (we'll use custom styling)
    root.option_add('*Button.Font', ('Segoe UI', 10))

    return colors

def create_modern_button(parent, text, command, style='primary', width=None):
    """Create a modern styled button with rounded corners and shadow effect"""
    colors = {
        'primary': {'bg': '#3498DB', 'fg': 'white', 'active_bg': '#2980B9', 'shadow': '#2471A3'},
        'success': {'bg': '#27AE60', 'fg': 'white', 'active_bg': '#229954', 'shadow': '#1E8449'},
        'secondary': {'bg': '#95A5A6', 'fg': 'white', 'active_bg': '#7F8C8D', 'shadow': '#707B7C'},
        'danger': {'bg': '#E74C3C', 'fg': 'white', 'active_bg': '#C0392B', 'shadow': '#A93226'}
    }

    btn_style = colors.get(style, colors['primary'])

    # Create a frame to hold the button with shadow effect
    btn_container = ttk.Frame(parent, style='TFrame')

    # Create shadow frame (slightly offset)
    shadow_frame = ttk.Frame(btn_container)
    shadow_frame.configure(style='TFrame')

    btn = Button(btn_container, text=text, command=command,
                 bg=btn_style['bg'],
                 fg=btn_style['fg'],
                 activebackground=btn_style['active_bg'],
                 activeforeground='white',
                 relief='raised',
                 font=('Segoe UI', 9, 'bold'),
                 cursor='hand2',
                 padx=15,
                 pady=8,
                 borderwidth=1,
                 highlightthickness=0,
                 width=width if width else 0)

    # Hover effects with shadow
    def on_enter(e):
        btn['background'] = btn_style['active_bg']
        btn['relief'] = 'raised'

    def on_leave(e):
        btn['background'] = btn_style['bg']
        btn['relief'] = 'raised'

    def on_press(e):
        btn['relief'] = 'sunken'

    def on_release(e):
        btn['relief'] = 'raised'

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.bind("<ButtonPress-1>", on_press)
    btn.bind("<ButtonRelease-1>", on_release)

    btn.pack()

    return btn_container

# ----------------------------------------------------------------------
# Close App
# ----------------------------------------------------------------------
def close_app(root):
    root.destroy()

# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------
def build_gui():
    global root, output_tree, log_text
    root = Tk()
    root.title("Sigma Parts Builder – v1.9.61")
    root.geometry("1400x750")
    root.minsize(1100, 550)

    # Apply professional theme
    colors = apply_professional_theme(root)
    root.configure(bg=colors['background'])

    # Main container with padding
    main_container = ttk.Frame(root, style='TFrame')
    main_container.pack(fill="both", expand=True, padx=10, pady=10)

    # Header section
    header = ttk.Frame(main_container, style='TFrame')
    header.pack(fill="x", pady=(0, 10))

    title_label = ttk.Label(header, text="Sigma Parts Builder", style='Title.TLabel')
    title_label.pack(side="left")

    version_label = ttk.Label(header, text="v1.9.61", style='Subtitle.TLabel')
    version_label.pack(side="left", padx=(8, 0))

    # Notebook with tabs
    nb = ttk.Notebook(main_container)
    nb.pack(fill="both", expand=True)

    # ---------- Control ----------
    ctrl = ttk.Frame(nb, style='TFrame')
    nb.add(ctrl, text="  Control  ")

    # Control panel container with padding
    ctrl_container = ttk.Frame(ctrl, style='TFrame')
    ctrl_container.pack(fill="both", expand=True, padx=15, pady=15)

    # Instruction section
    instruction_frame = ttk.Frame(ctrl_container, style='TFrame')
    instruction_frame.pack(fill="x", pady=(0, 12))

    instruction_label = ttk.Label(instruction_frame,
                                  text="Follow the steps below to process your parts data",
                                  style='Subtitle.TLabel')
    instruction_label.pack(anchor="w")

    # Workflow steps with modern cards
    steps_frame = ttk.Frame(ctrl_container, style='TFrame')
    steps_frame.pack(fill="x", pady=(0, 10))

    # Create step buttons in a grid layout
    step_data = [
        ("1", "Import CHP Entry Data", "Import any CHP entry CSV file", import_chp, 'primary'),
        ("2", "Import Sigma Parts List", "Import Sigma parts with client code", import_sigma_parts, 'primary'),
        ("3", "Import MID List", "Import manufacturer ID list", import_mid_list, 'primary'),
        ("4", "Process Data", "Process & view the output", process_and_export, 'success'),
        ("5", "Export Upload File", "Export Sigma upload format", export_sigma_upload, 'secondary'),
    ]

    for i, (num, title, desc, cmd, btn_style) in enumerate(step_data):
        step_card = ttk.Frame(steps_frame, style='TFrame')
        step_card.pack(fill="x", pady=3)

        # Step number and button
        btn_frame = ttk.Frame(step_card, style='TFrame')
        btn_frame.pack(fill="x")

        step_num_label = ttk.Label(btn_frame, text=f"Step {num}",
                                    font=('Segoe UI', 8, 'bold'),
                                    foreground='#7F8C8D',
                                    background=colors['background'])
        step_num_label.pack(side="left", padx=(0, 8))

        btn = create_modern_button(btn_frame, title, cmd, style=btn_style, width=30)
        btn.pack(side="left")

        desc_label = ttk.Label(btn_frame, text=f"  ({desc})",
                               font=('Segoe UI', 8, 'italic'),
                               foreground='#95A5A6',
                               background=colors['background'])
        desc_label.pack(side="left", padx=(8, 0))

    # Separator
    separator = ttk.Separator(ctrl_container, orient='horizontal')
    separator.pack(fill="x", pady=10)

    # Progress Log section
    log_frame = ttk.LabelFrame(ctrl_container, text="  Progress Log  ", style='TLabelframe')
    log_frame.pack(fill="both", expand=True, pady=(0, 10))

    log_inner = ttk.Frame(log_frame, style='TFrame')
    log_inner.pack(fill="both", expand=True, padx=8, pady=8)

    log_text = Text(log_inner, height=12, wrap="word", state="normal",
                    bg='#FFFFFF', fg='#2C3E50',
                    font=('Consolas', 8),
                    relief='flat',
                    borderwidth=0,
                    insertbackground='#3498DB')
    log_text.pack(side="left", fill="both", expand=True)

    sb_log = Scrollbar(log_inner, command=log_text.yview)
    sb_log.pack(side="right", fill="y")
    log_text.config(yscrollcommand=sb_log.set)

    # Bottom action buttons
    bottom_frame = ttk.Frame(ctrl_container, style='TFrame')
    bottom_frame.pack(fill="x")

    close_btn = create_modern_button(bottom_frame, "Close Application",
                                      lambda: close_app(root), style='danger', width=18)
    close_btn.pack(side="right")

    # ---------- Output ----------
    outf = ttk.Frame(nb, style='TFrame')
    nb.add(outf, text="  Output  ")

    # Output container with padding
    output_container = ttk.Frame(outf, style='TFrame')
    output_container.pack(fill="both", expand=True, padx=15, pady=15)

    # Header section with title and action buttons
    output_header = ttk.Frame(output_container, style='TFrame')
    output_header.pack(fill="x", pady=(0, 10))

    output_title = ttk.Label(output_header, text="Final Report", style='Title.TLabel')
    output_title.pack(side="left")

    # Action buttons on the right
    btn_container = ttk.Frame(output_header, style='TFrame')
    btn_container.pack(side="right")

    export_btn = create_modern_button(btn_container, "📊 Export to Excel",
                                       export_output_excel, style='success', width=16)
    export_btn.pack(side="left", padx=3)

    copy_btn = create_modern_button(btn_container, "📋 Copy to Clipboard",
                                     copy_output_to_clipboard, style='secondary', width=16)
    copy_btn.pack(side="left", padx=3)

    # Data grid section with frame
    grid_frame = ttk.Frame(output_container, style='TFrame')
    grid_frame.pack(fill="both", expand=True)

    # Treeview with columns
    cols = ("Product No","MID","Vendor","HTS","COO","232 Steel","232 Alum","232 Copper","232 Auto","232 Wood","Date","First Cust. Ref.","File No.","Customer ID")
    output_tree = ttk.Treeview(grid_frame, columns=cols, show="headings", style='Treeview')
    widths = [120,100,180,100,60,70,70,70,70,70,130,120,100,100]
    for c, w in zip(cols, widths):
        output_tree.heading(c, text=c)
        output_tree.column(c, width=w, anchor="w")

    # Add scrollbars
    vsb = Scrollbar(grid_frame, command=output_tree.yview, orient='vertical')
    hsb = Scrollbar(grid_frame, command=output_tree.xview, orient='horizontal')
    output_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    # Grid layout for treeview and scrollbars
    output_tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')

    grid_frame.grid_rowconfigure(0, weight=1)
    grid_frame.grid_columnconfigure(0, weight=1)

    # Status label for row count
    status_frame = ttk.Frame(output_container, style='TFrame')
    status_frame.pack(fill="x", pady=(10, 0))

    output_status_label = ttk.Label(status_frame,
                                     text="No data loaded. Run 'Process Data' to view results.",
                                     font=('Segoe UI', 9, 'italic'),
                                     foreground='#7F8C8D',
                                     background=colors['background'])
    output_status_label.pack(side="left")

    # ---------- Log ----------
    logf = ttk.Frame(nb, style='TFrame')
    nb.add(logf, text="  Error Log  ")

    # Log container with padding
    log_container = ttk.Frame(logf, style='TFrame')
    log_container.pack(fill="both", expand=True, padx=15, pady=15)

    # Header
    log_header = ttk.Frame(log_container, style='TFrame')
    log_header.pack(fill="x", pady=(0, 10))

    log_title = ttk.Label(log_header, text="System Log", style='Title.TLabel')
    log_title.pack(side="left")

    log_subtitle = ttk.Label(log_header,
                             text="Track errors and system events",
                             font=('Segoe UI', 9),
                             foreground='#7F8C8D',
                             background=colors['background'])
    log_subtitle.pack(side="left", padx=(10, 0))

    # Log grid section
    log_grid_frame = ttk.Frame(log_container, style='TFrame')
    log_grid_frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(log_grid_frame, columns=("Type","Product No","MID","Details"),
                        show="headings", style='Treeview')
    for c, w in zip(tree["columns"], [100, 150, 120, 550]):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")

    # Add scrollbars
    log_vsb = Scrollbar(log_grid_frame, command=tree.yview, orient='vertical')
    log_hsb = Scrollbar(log_grid_frame, command=tree.xview, orient='horizontal')
    tree.configure(yscrollcommand=log_vsb.set, xscrollcommand=log_hsb.set)

    # Grid layout
    tree.grid(row=0, column=0, sticky='nsew')
    log_vsb.grid(row=0, column=1, sticky='ns')
    log_hsb.grid(row=1, column=0, sticky='ew')

    log_grid_frame.grid_rowconfigure(0, weight=1)
    log_grid_frame.grid_columnconfigure(0, weight=1)

    nb.bind("<<NotebookTabChanged>>", lambda e: refresh_log(tree) if nb.index(nb.select())==2 else None)

    # Modern status bar at the bottom of main window
    status_bar = ttk.Frame(root, style='TFrame', relief='flat')
    status_bar.pack(side="bottom", fill="x")

    # Status bar background
    status_inner = ttk.Frame(status_bar, style='TFrame')
    status_inner.pack(fill="x", padx=10, pady=6)

    status = Label(status_inner, text="Ready",
                   anchor="w",
                   bg=colors['primary'],
                   fg='white',
                   font=('Segoe UI', 8),
                   padx=8,
                   pady=4,
                   relief='flat')
    status.pack(side="left", fill="x", expand=True)

    root.set_status = lambda txt: status.config(text=txt)

    return root

# ----------------------------------------------------------------------
# Output Tab – SHOWS FIRST CUST REF & FILE NO
# ----------------------------------------------------------------------
def refresh_output_tab():
    global OUTPUT_DF
    if OUTPUT_DF is None:
        return
    for i in output_tree.get_children():
        output_tree.delete(i)
    for _, row in OUTPUT_DF.iterrows():
        output_tree.insert("", "end", values=(
            row['product_no'], row['mid'], row['vendor_name'],
            row['final_hts'], row['coo'], 
            row.get('sec_232_steel', ''), row.get('sec_232_aluminum', ''),
            row.get('sec_232_copper', ''), row.get('sec_232_auto_parts', ''),
            row.get('sec_232_wood', ''), row['date_added'],
            row.get('first_cust_ref', ''), row.get('file_no', ''), row.get('customer_id', '')
        ))

def export_output_excel():
    if OUTPUT_DF is None:
        messagebox.showinfo("Info", "No output to export.")
        return
    path = filedialog.asksaveasfilename(
        title="Save Output Excel", defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")]
    )
    if path:
        try:
            # Ensure customer_id column exists
            if 'customer_id' not in OUTPUT_DF.columns:
                OUTPUT_DF['customer_id'] = ''
            out = OUTPUT_DF[['product_no','mid','vendor_name','final_hts',
                             'coo','sec_232_steel','sec_232_aluminum','sec_232_copper',
                             'sec_232_auto_parts','sec_232_wood','date_added',
                             'first_cust_ref','file_no','customer_id']].copy()
            out.columns = ['Product No','MID','Last purchase vendor name','FINAL HTS',
                           'COO','SEC 232 STEEL','SEC 232 ALUMINUM','SEC 232 COPPER',
                           'SEC 232 AUTO PARTS','SEC 232 WOOD','Date Added',
                           'First Cust. Ref.','File No.','Customer ID']
            out.to_excel(path, index=False, engine='openpyxl')
            messagebox.showinfo("Success", f"Exported to:\n{path}")
            log("INFO", "", "", f"Output exported to Excel: {path}")
        except Exception as e:
            log("ERROR","","",f"Export failed: {e}")

def copy_output_to_clipboard():
    if OUTPUT_DF is None or not PYPERCLIP_AVAILABLE:
        messagebox.showinfo("Info", "No output or pyperclip not available.")
        return
    try:
        # Ensure customer_id column exists
        if 'customer_id' not in OUTPUT_DF.columns:
            OUTPUT_DF['customer_id'] = ''
        out = OUTPUT_DF[['product_no','mid','vendor_name','final_hts',
                         'coo','sec_232_steel','sec_232_aluminum','sec_232_copper',
                         'sec_232_auto_parts','sec_232_wood','date_added',
                         'first_cust_ref','file_no','customer_id']].copy()
        out.columns = ['Product No','MID','Last purchase vendor name','FINAL HTS',
                       'COO','SEC 232 STEEL','SEC 232 ALUMINUM','SEC 232 COPPER',
                       'SEC 232 AUTO PARTS','SEC 232 WOOD','Date Added',
                       'First Cust. Ref.','File No.','Customer ID']
        out.to_clipboard(index=False)
        messagebox.showinfo("Success", "Copied to clipboard!")
    except Exception as e:
        log("ERROR","","",f"Copy failed: {e}")

# ----------------------------------------------------------------------
# Error Log Display – SHOWS PRODUCT NO
# ----------------------------------------------------------------------
def refresh_log(tree):
    for i in tree.get_children():
        tree.delete(i)
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM debug_log ORDER BY timestamp DESC", conn)
        for _, r in df.iterrows():
            tree.insert("", "end", values=(r['log_type'], r['product_no'], r['mid'], r['details']))
    finally:
        conn.close()

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    try:
        init_db()
        global root
        root = build_gui()
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"Application Error:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            messagebox.showerror("Application Error", error_msg)
        except:
            pass
        raise

if __name__ == "__main__":
    main()
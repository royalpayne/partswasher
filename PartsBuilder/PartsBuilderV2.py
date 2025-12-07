# PartsBuilderV2.py
# Version: v1.9.55 – Customer ID Fix
# Author: Assistant
# Date: 2025-12-07
# --------------------------------------------------------------
#  • If vendor_name missing → use MID → lookup ven_name
#  • First Cust. Ref. & File No. in GUI
#  • Export Sigma Upload unchanged
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
# 1. Import CHP – SIGMA_COO_ALL*.csv Format
# ----------------------------------------------------------------------
def import_chp():
    def job():
        path = filedialog.askopenfilename(title="Select SIGMA_COO_ALL*.csv", filetypes=[("CSV Files", "*.csv")])
        if not path: return

        try:
            df = pd.read_csv(path)
            log("INFO", "", "", f"CHP CSV loaded: {len(df)} rows")

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
                messagebox.showerror("Error", f"Missing columns in SIGMA_COO_ALL.csv:\n{missing}\n\nFound: {list(df.columns)}")
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
        df = pd.read_excel(MID_XLSX, header=None, usecols=[0,1])
        df.columns = ['ven_mid','ven_name']
        df['ven_mid'] = df['ven_mid'].astype(str).str.strip().str.upper()
        df['ven_name'] = df['ven_name'].astype(str).str.strip()
        df = df[df['ven_mid'].str.len() > 0]
        conn = sqlite3.connect(DB_FILE)
        df.to_sql('sigma_mid_list', conn, if_exists='replace', index=False)
        conn.close()
        log("INFO", "", "", "MID list imported")
        messagebox.showinfo("Success", "MID list imported")
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
        c.execute("""
            UPDATE sigma_parts
            SET mid = (
                SELECT ven_mid FROM sigma_mid_list
                WHERE UPPER(TRIM(sigma_mid_list.ven_name)) = UPPER(TRIM(sigma_parts.vendor_name))
            )
            WHERE mid IS NULL OR mid = ''
        """)
        mid_updated = c.rowcount
        conn.commit()
        conn.close()

        # Reload updated data
        conn = sqlite3.connect(DB_FILE)
        parts = pd.read_sql_query("SELECT * FROM sigma_parts", conn)
        conn.close()

        if mid_updated > 0:
            log("INFO", "", "", f"Populated {mid_updated} MIDs from vendor_name")

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
    root.title("Sigma Parts Builder – v1.9.55")
    root.geometry("1400x750")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    # ---------- Control ----------
    ctrl = ttk.Frame(nb)
    nb.add(ctrl, text="Control")
    Label(ctrl, text="Import to Process to Export", font=("Arial",12,"bold")).pack(pady=8)

    log_frame = ttk.LabelFrame(ctrl, text="Progress Log")
    log_frame.pack(fill="both", expand=True, padx=10, pady=5)
    log_text = Text(log_frame, height=12, wrap="word", state="normal")
    log_text.pack(side="left", fill="both", expand=True)
    sb_log = Scrollbar(log_frame, command=log_text.yview)
    sb_log.pack(side="right", fill="y")
    log_text.config(yscrollcommand=sb_log.set)

    btns = [
        ("1. Import SIGMA_COO_ALL*.csv", import_chp),
        ("2. Import Sigma Parts List", import_sigma_parts),
        ("3. Import MID List", import_mid_list),
        ("4. Process & View Output", process_and_export),
        ("5. Export Sigma Upload (A,I,J,L,Q,AA,AB)", export_sigma_upload),
        ("Close", lambda: close_app(root))
    ]
    for txt, cmd in btns:
        Button(ctrl, text=txt, command=cmd, width=50).pack(pady=3)

    # ---------- Output ----------
    outf = ttk.Frame(nb)
    nb.add(outf, text="Output")
    Label(outf, text="Final Report", font=("Arial",11,"bold")).pack(pady=8)
    cols = ("Product No","MID","Vendor","HTS","COO","232 Steel","232 Alum","232 Copper","232 Auto","232 Wood","Date","First Cust. Ref.","File No.","Customer ID")
    output_tree = ttk.Treeview(outf, columns=cols, show="headings")
    widths = [120,100,180,100,60,70,70,70,70,70,130,120,100,100]
    for c, w in zip(cols, widths):
        output_tree.heading(c, text=c)
        output_tree.column(c, width=w, anchor="w")
    output_tree.pack(side="left", fill="both", expand=True)
    Scrollbar(outf, command=output_tree.yview).pack(side="right", fill="y")

    btn_frame = ttk.Frame(outf)
    btn_frame.pack(pady=8)
    Button(btn_frame, text="Export to Excel", command=export_output_excel).pack(side="left", padx=5)
    Button(btn_frame, text="Copy to Clipboard", command=copy_output_to_clipboard).pack(side="left", padx=5)

    # ---------- Log ----------
    logf = ttk.Frame(nb)
    nb.add(logf, text="Error Log")
    tree = ttk.Treeview(logf, columns=("Type","Product No","MID","Details"), show="headings")
    for c,w in zip(tree["columns"],[80,130,100,450]):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    tree.pack(side="left", fill="both", expand=True)
    Scrollbar(logf, command=tree.yview).pack(side="right", fill="y")
    nb.bind("<<NotebookTabChanged>>", lambda e: refresh_log(tree) if nb.index(nb.select())==2 else None)

    status = Label(root, text="Ready", anchor="w", relief="sunken", bd=1)
    status.pack(side="bottom", fill="x")
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
            out.to_excel(path, index=False)
            messagebox.showinfo("Success", f"Exported to:\n{path}")
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
    init_db()
    global root
    root = build_gui()
    root.mainloop()

if __name__ == "__main__":
    main()
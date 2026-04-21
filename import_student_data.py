import pandas as pd
import sqlite3
import os

# Configuration
DB_FILE = 'student_system_final_v2.db'
EXCEL_FILE = '学生名单.xls'

def import_data():
    # Check if files exist
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: Excel file '{EXCEL_FILE}' not found.")
        return
    
    print(f"Reading Excel file: {EXCEL_FILE}...")
    try:
        # Read Excel file
        df = pd.read_excel(EXCEL_FILE)
        print(f"Successfully read {len(df)} rows from Excel.")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    print(f"Connecting to database: {DB_FILE}...")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    # Prepare data for insertion
    success_count = 0
    error_count = 0
    
    print("Starting data import...")
    for index, row in df.iterrows():
        try:
            # Extract fields
            student_id = str(row['学号']).strip()
            name = str(row['姓名']).strip()
            grade = str(row['年级']).strip()
            major = str(row['专业']).strip()
            class_name = str(row['班级']).strip()
            gender = str(row['性别']).strip()
            
            # Default values
            password = "123456"
            role = "成员"
            status = "在读"
            contact = ""
            group_name = None

            # Insert into database
            cursor.execute('''
                INSERT OR REPLACE INTO students 
                (id, name, password, gender, major, class_name, grade, contact, status, role, group_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, name, password, gender, major, class_name, grade, contact, status, role, group_name))
            
            success_count += 1
        except Exception as e:
            print(f"Error inserting row {index + 2}: {e}")
            error_count += 1

    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"Import completed.")
    print(f"Successfully imported: {success_count}")
    print(f"Errors: {error_count}")
    print("-" * 30)

if __name__ == "__main__":
    import_data()

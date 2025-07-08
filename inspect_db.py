import sqlite3

db_path = "master.db"
output_file = "master_db_contents.txt"

def list_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]

def print_table_contents(cursor, table, f):
    f.write(f"\nTable: {table}\n")
    cursor.execute(f'PRAGMA table_info("{table}");')
    columns = [col[1] for col in cursor.fetchall()]
    f.write("Columns: " + ", ".join(columns) + "\n")
    cursor.execute(f'SELECT * FROM "{table}" LIMIT 5;')
    rows = cursor.fetchall()
    for row in rows:
        f.write(str(row) + "\n")

def main():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    tables = list_tables(cursor)
    with open(output_file, "w", encoding="utf-8") as f:
        if not tables:
            f.write("No tables found in the database.\n")
        else:
            for table in tables:
                print_table_contents(cursor, table, f)
    conn.close()
    print(f"Database contents saved to {output_file}")

if __name__ == "__main__":
    main()
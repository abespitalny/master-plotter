import argparse
import sqlite3
import pandas as pd
import numpy as np
import pathlib
import time

# removes any '`' from string and returns result unless the string is now empty 
def parse_name(s, def_val):
    s = s.replace('`', '')
    return def_val if s == '' else s

def main(args):
    start = time.time()
    conn = None
    try:
        # create or open database specified by args.output
        conn = sqlite3.connect(args.output)
        input_file = pathlib.Path(args.input)
        df = pd.read_csv(input_file)
        
        # table name is taken from the name of the CSV file without the extension
        # (note: if the file is named just ".csv" then the table name will be ".csv")
        table_name = parse_name(input_file.stem, "data")
        header_names = df.columns.values
        if header_names.size == 0:
            raise ValueError("There are zero headers in the CSV file")
        # specified as {COL_NAME: COL_TYPE, ...}
        table_cols = [[None]*2 for i in range(header_names.size)]
        for i, h in enumerate(header_names):
            col_name = parse_name(h, "col" + str(i+1))
            col_type = "TEXT"
            if np.issubdtype(df.dtypes[h], np.integer):
                col_type = "INTEGER"
            elif np.issubdtype(df.dtypes[h], np.floating):
                col_type = "REAL"
            
            table_cols[i][0] = col_name
            table_cols[i][1] = col_type
        
        # create table in database if it does not exist
        sql_table_cols = ','.join(map(lambda c: f"`{c[0]}` {c[1]}", table_cols))
        sql_create_data_table = f"CREATE TABLE IF NOT EXISTS `{table_name}` (id INTEGER PRIMARY KEY,{sql_table_cols});"
        cur = conn.cursor()
        cur.execute(sql_create_data_table)

        # truncate the table
        sql_truncate_table = f"DELETE FROM `{table_name}`;"
        cur.execute(sql_truncate_table)
        conn.commit()

        # get any indices that might exist for this table
        sql_get_indices = f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?;"
        # passing in table_name into execute to be properly escaped allows for the table_name to contain single quotes
        cur.execute(sql_get_indices, (table_name,))
        old_indices = cur.fetchall()
        # drop these indices
        sql_drop_index = "DROP INDEX `{}`;"
        for i in old_indices:
            cur.execute(sql_drop_index.format(i[0]))

        sql_table_cols = ','.join(map(lambda c: f"`{c[0]}`", table_cols))
        sql_insert_row = f"INSERT INTO `{table_name}` ({sql_table_cols}) VALUES ({','.join(['?']*(header_names.size))});"
        cur.executemany(sql_insert_row, df.itertuples(index=False, name=None))

        # dropping and recreating the indices after this large batch import of data
        # leads to better performance and makes for more general code
        # because then indices are not static and can be changed
        sql_create_index = f"CREATE INDEX `{{}}` ON `{table_name}` ({{}});"
        for i, n in enumerate(args.index):
            cur.execute(sql_create_index.format("idx_" + str(i), ','.join(map(lambda c: f"`{c}`", n))))

        conn.commit()
    except Exception as e:
        if conn is not None:
            conn.rollback()
        print(e)
    finally:
        if conn is not None:
            conn.close()
    end = time.time()
    print(f"Time for completion: {end - start}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="path to CSV input file", required=True)
    parser.add_argument("-o", "--output", help="path to SQLite output file", default="db.sqlite")
    parser.add_argument("-x", "--index", help="specify the columns that will have an index on them", action="append", nargs="*", default=[])
    args = parser.parse_args()
    main(args)

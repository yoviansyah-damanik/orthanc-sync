import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

db_host = os.getenv('DB_HOST', '127.0.0.1')
db_user = os.getenv('DB_USER', 'root')
db_pass = os.getenv('DB_PASSWORD', '')
db_port = int(os.getenv('DB_PORT', '3307'))

try:
    conn = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        port=db_port
    )
    with conn.cursor() as cursor:
        cursor.execute("SHOW DATABASES;")
        dbs = cursor.fetchall()
        print("Databases found:")
        for db in dbs:
            print(f"- {db[0]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")

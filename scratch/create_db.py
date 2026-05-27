import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

db_host = os.getenv('DB_HOST', '127.0.0.1')
db_user = os.getenv('DB_USER', 'root')
db_pass = os.getenv('DB_PASSWORD', '')
db_port = int(os.getenv('DB_PORT', '3307'))
db_name = os.getenv('DB_NAME', 'orthanc_sync')

try:
    # Connect without database name
    conn = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        port=db_port
    )
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET latin1 COLLATE latin1_swedish_ci;")
    conn.close()
    print(f"Database '{db_name}' ensured.")
except Exception as e:
    print(f"Error creating database: {e}")

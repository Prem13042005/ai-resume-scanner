import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='WJ28@krhps',
        database='ai_resume_scanner_db'
    )

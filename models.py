"""
数据库模型定义

使用方法：
from models import init_db, save_request_log
"""

import sqlite3
from datetime import datetime
from contextlib import closing
import os

DB_PATH = os.environ.get('DB_PATH', 'jieba_stats.db')

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库"""
    with closing(get_db_connection()) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_time REAL NOT NULL,
                mode TEXT,
                text_length INTEGER
            )
        ''')
        conn.commit()

def save_request_log(endpoint, method, status_code, response_time, mode=None, text_length=None):
    """保存请求日志"""
    with closing(get_db_connection()) as conn:
        conn.execute('''
            INSERT INTO request_log (timestamp, endpoint, method, status_code, response_time, mode, text_length)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now(), endpoint, method, status_code, response_time, mode, text_length))
        conn.commit()

def get_stats():
    """获取统计数据"""
    with closing(get_db_connection()) as conn:
        total = conn.execute('SELECT COUNT(*) as count FROM request_log').fetchone()['count']
        avg_time = conn.execute('SELECT AVG(response_time) as avg FROM request_log').fetchone()['avg'] or 0
        hourly = conn.execute('''
            SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*) as count
            FROM request_log
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
        ''').fetchall()
        mode_dist = conn.execute('''
            SELECT mode, COUNT(*) as count
            FROM request_log
            WHERE mode IS NOT NULL
            GROUP BY mode
        ''').fetchall()
        recent = conn.execute('''
            SELECT * FROM request_log
            ORDER BY timestamp DESC
            LIMIT 50
        ''').fetchall()

        return {
            'total': total,
            'avg_time': round(avg_time, 3),
            'hourly': [dict(row) for row in hourly],
            'mode_dist': [dict(row) for row in mode_dist],
            'recent': [dict(row) for row in recent]
        }

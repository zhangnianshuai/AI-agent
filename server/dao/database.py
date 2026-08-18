import pymysql
from dbutils.pooled_db import PooledDB
from server.config import settings
from contextlib import contextmanager


class Database:
    """数据库连接管理"""

    def __init__(self):
        self._pool = PooledDB(
            creator=pymysql,            # 指定连接库
            maxconnections=30,          # 连接池最大连接数
            mincached=2,                # 初始化时创建的空闲连接数
            maxcached=10,               # 空闲连接池最大数
            blocking=True,              # 连接池满时阻塞等待，而非立即报错
            maxusage=100,               # 单个连接最大复用次数，防止脏状态累积
            setsession=[],              # 开始会话时的SQL命令
            ping=1,                     # 连接首次使用时 ping，避免每次额外的网络往返
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def get_conn(self):
        """获取新连接"""
        return self._pool.connection()

    def execute(self, sql: str, params=None):
        """执行增删改，返回影响行数"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                rows = cursor.execute(sql, params)
            conn.commit()
            return rows
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql: str, params=None, one: bool = False):
        """执行查询，one=True返回单条"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone() if one else cursor.fetchall()
        finally:
            conn.close()
            
    @contextmanager
    def transaction(self):
        conn = self.get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# 全局单例
db = Database()

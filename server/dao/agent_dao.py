from server.dao.database import db
from server.models.agent import agent_config
from server.utils.sql_builder import build_set

class AgentConfigDao:
    """Agent面试官配置表 DAO"""
    # model_dump 时排除的数据库自动维护字段
    _DB_MANAGED_FIELDS = {'created_at', 'updated_at', 'deleted_at'}

    def get_config_by_id(self, config_id: int) -> 'agent_config | None':
        """按 ID 查询单条配置"""
        sql = "SELECT * FROM agent_config WHERE id = %s"
        row = db.query(sql, params=(config_id,), one=True)
        if row is None:
            return None
        return agent_config.model_validate(row)

    def list_configs(self) -> 'list[agent_config]':
        """查询全部配置"""
        sql = "SELECT * FROM agent_config ORDER BY id DESC"
        rows = db.query(sql)
        return [agent_config.model_validate(row) for row in rows]

    def create_config(self, config: 'agent_config', conn=None) -> int:
        """新建配置（含 Snowflake ID），返回影响行数

        conn: 可选，传入则使用该连接执行（不提交），否则走 db.execute()
        """
        data = config.model_dump(exclude=self._DB_MANAGED_FIELDS)
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO agent_config ({columns}) VALUES ({placeholders})"
        if conn is not None:
            with conn.cursor() as cursor:
                return cursor.execute(sql, tuple(data.values()))
        return db.execute(sql, tuple(data.values()))

    def update_config(self, config_id: int, config: 'agent_config') -> int:
        """更新指定字段（仅更新非空字段），返回影响行数"""
        data = config.model_dump(exclude_none=True, exclude={'id'} | self._DB_MANAGED_FIELDS)
        if not data:
            return 0
        sets, params = build_set(**data)
        params.append(config_id)
        return db.execute(f"UPDATE agent_config SET {sets} WHERE id = %s", tuple(params))

    def delete_config(self, config_id: int) -> int:
        """删除配置，返回影响行数"""
        sql = "DELETE FROM agent_config WHERE id = %s"
        return db.execute(sql, (config_id,))
    
    def get_config_by_type(self, config_type: str) -> 'agent_config | None':
        """按类型查询配置（sql_admin 类型保证唯一）"""
        sql = "SELECT * FROM agent_config WHERE type = %s LIMIT 1"
        row = db.query(sql, params=(config_type,), one=True)
        if row is None:
            return None
        return agent_config.model_validate(row)

    def get_config_by_job_id(self, job_id: int) -> 'agent_config | None':
        """按岗位 ID 查询该岗位绑定的 Agent 配置（通过 job_position.agent_config_id 关联）"""
        sql = """SELECT ac.* FROM agent_config ac
                 INNER JOIN job_position jp ON jp.agent_config_id = ac.id
                 WHERE jp.id = %s"""
        row = db.query(sql, params=(job_id,), one=True)
        if row is None:
            return None
        return agent_config.model_validate(row)

    def list_configs_with_job_info(self) -> list[dict]:
        """查询全部配置，附带关联的公司名和岗位名"""
        sql = """SELECT ac.*, jp.id AS job_id, jp.title AS job_title,
                        c.id AS company_id, c.name AS company_name
                 FROM agent_config ac
                 LEFT JOIN job_position jp ON jp.agent_config_id = ac.id
                 LEFT JOIN company c ON jp.company_id = c.id
                 ORDER BY ac.id DESC"""
        return db.query(sql)


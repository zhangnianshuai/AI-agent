from typing import Optional
from server.models.base import BaseEntity  
from pydantic import BaseModel


class Job(BaseEntity):
    """岗位表 (job_position)"""
    title: str                                      # 岗位名称
    company_id: int                                 # 所属企业 ID
    agent_config_id: Optional[int] = None           # 绑定的 Agent 面试官配置 ID
    question_bank_partition: Optional[str] = None   # 题库分区标识
    description: Optional[str] = None               # 岗位描述 (JD)
    salary_min: Optional[int] = None                # 薪资下限 (单位: 千元)
    salary_max: Optional[int] = None                # 薪资上限 (单位: 千元)
    location: Optional[str] = None                  # 工作地点
    category: Optional[str] = None                  # 岗位分类 (如 后端/前端/算法)
    education_requirement: Optional[str] = None     # 学历要求 (如 本科/硕士)
    experience_requirement: Optional[str] = None    # 经验要求 (如 3-5年)
    headcount: int = 1                              # 招聘人数
    status: int = 1                                 # 状态: 0=关闭, 1=开放

class JobItem(BaseModel):
    """岗位搜索结果项（岗位字段 + 公司字段）"""
    job_id: int
    title: str
    description: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    category: str | None = None
    education_requirement: str | None = None
    experience_requirement: str | None = None
    headcount: int = 0
    status: int = 1
    # 公司信息
    company_id: int
    company_name: str = ""
    industry: str | None = None
    scale: str | None = None

from typing import Literal

from pydantic import BaseModel, Field, model_validator

#登录注册请求
class LoginRequest(BaseModel):
    username: str 
    password: str 

class RegisterRequest(BaseModel):
    username: str 
    password: str
    email: str | None=None
    phone: str | None=None

#简历上传请求
class ResumeUploadRequest(BaseModel):
    file_name: str = ""      # 新加
    file_url: str = ""       # 新加
    name: str = ""
    age: int | None = 0
    sex: str | None = "男"
    work_year: str | None = "无工作经验"
    skills: str = ""
    self_evaluation: str = ""
    job_intention: str = ""  # 新加
    education: list[dict] = []
    projects: list[dict] = []

    @model_validator(mode="after")
    def apply_defaults_on_null(self):
        if self.age is None:
            self.age = 0
        if self.sex is None:
            self.sex = "男"
        if self.work_year is None:
            self.work_year = "无工作经验"
        return self


class EducationUpdateItem(BaseModel):
    school_name: str = Field(default="", max_length=256)
    degree: str = Field(default="", max_length=64)
    major: str = Field(default="", max_length=256)
    start_date: str = Field(default="", max_length=32)
    end_date: str = Field(default="", max_length=32)


class ProjectUpdateItem(BaseModel):
    project_name: str = Field(default="", max_length=256)
    description: str = ""
    role: str = Field(default="", max_length=128)
    start_date: str = Field(default="", max_length=32)
    end_date: str = Field(default="", max_length=32)


class ResumeUpdateRequest(BaseModel):
    """已保存简历的完整可编辑内容。"""

    name: str = Field(max_length=64)
    age: int = Field(ge=0, le=120)
    sex: str = Field(max_length=16)
    work_year: str = Field(max_length=32)
    skills: str
    self_evaluation: str
    job_intention: str = Field(max_length=256)
    education: list[EducationUpdateItem]
    projects: list[ProjectUpdateItem]

#岗位相关请求
class JobCreateRequest(BaseModel):
    company_id: int                            # 所属公司ID
    agent_config_id: int | None = None
    title: str
    description: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    category: str | None = None
    education_requirement: str | None = None
    experience_requirement: str | None = None
    headcount: int = 1

    @model_validator(mode="after")
    def validate_salary_range(self):
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min >= self.salary_max:
                raise ValueError("salary_min 必须小于 salary_max")
        return self

class JobSearchRequest(BaseModel):
    """岗位搜索请求：所有筛选参数可选，不传即全量分页"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=5, ge=1, le=100, description="每页数量")
    keyword: str | None = Field(default=None, description="模糊搜索 title + description")
    location: str | None = Field(default=None, description="工作地点精确匹配")
    category: str | None = Field(default=None, description="岗位分类精确匹配")
    education_requirement: str | None = Field(default=None, description="学历要求精确匹配")
    experience_requirement: str | None = Field(default=None, description="经验要求精确匹配")
    company_id: int | None = Field(default=None, description="公司ID精确匹配")

class QuestionCreateRequest(BaseModel):
    company_id: int
    job_id: int

class QuestionGetRequest(BaseModel):
    company_id: int
    job_id: int
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=5, ge=1, le=200, description="每页数量")

class QuestionUpdateRequest(BaseModel):
    company_id: int
    pk: str = Field(..., description="题目主键 MD5")
    question: str | None = None
    answer: str | None = None
    scoring_criteria: str | None = None
    difficulty: int | None = None

class QuestionDeleteRequest(BaseModel):
    company_id: int
    pk: str = Field(..., description="题目主键 MD5")

#公司相关请求
class CompanyCreateRequest(BaseModel):
    name: str                                  # 公司全称
    short_name: str | None = None              # 公司简称
    industry: str | None = None                # 所属行业
    scale: str | None = None                   # 公司规模
    description: str | None = None             # 公司简介
    address: str | None = None                 # 公司地址
    website: str | None = None                 # 公司官网
    logo_url: str | None = None                # Logo地址
    contact_person: str | None = None          # 联系人
    contact_phone: str | None = None           # 联系电话

#角色控制相关请求
class UpdateRoleRequest(BaseModel):
    user_id: int
    role: Literal["candidate", "hr"]

class UpdateStatusRequest(BaseModel):
    user_id: int
    status: Literal[0, 1]  # 0=禁用, 1=正常

#用户修改个人信息请求
class UpdateUserInfoRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    real_name: str | None = None
    avatar_url: str | None = None

#用户修改密码
class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str

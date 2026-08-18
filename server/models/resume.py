from server.models.base import BaseEntity


class Resume(BaseEntity):
    user_id: int
    name: str = ""
    age: int = 0
    sex: str = ""
    work_year: str = ""
    skills: str = ""
    self_evaluation: str = ""


class Education(BaseEntity):
    user_id: int
    resume_id: int
    school_name: str = ""
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""


class Project(BaseEntity):
    resume_id: int
    project_name: str = ""
    description: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""

from typing import Optional
from server.models.base import BaseEntity


class Company(BaseEntity):
    """公司企业表 (company)"""
    name: str
    short_name: Optional[str] = None
    milvus_db: str
    question_bank_collection: Optional[str] = None
    industry: Optional[str] = None
    scale: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    status: int = 1

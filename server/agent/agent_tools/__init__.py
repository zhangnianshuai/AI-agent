from .milvus_tools import search_question_bank
from .milvus_tools import search_milvus, list_milvus_collections, describe_milvus_collection
from .mysql_tools import query_mysql, update_status
from .interview_tools import save_interview_evaluation, save_interview_record
from .sys_tools import read_file, write_file, delete_file, list_directory
from .skill_tools import get_skills_list, get_skill_content
from .cmd_tools import (
    cmd_execute,
    check_service_status,
    restart_service,
    view_log,
    check_system_resources,
    health_check,
)

# 面试 Agent 工具列表
interview_tools_list = [
    search_question_bank,
    save_interview_record,
    save_interview_evaluation,
]

# 管理员 SQL Agent 工具列表
admin_tools_list = [
    query_mysql,
    update_status,
    search_milvus,
    list_milvus_collections,
    describe_milvus_collection,
    read_file,
    write_file,
    delete_file,
    list_directory,
    get_skills_list,
    get_skill_content,
    cmd_execute,
    check_service_status,
    restart_service,
    view_log,
    check_system_resources,
    health_check,
]

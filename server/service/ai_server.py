from server.config import settings
from server.utils.llm_utils import extract_json_from_reply, retry_on_failure

class LLMService:

    def __init__(self,llm):
        self.client = llm

    @retry_on_failure(max_retries=3, delay=1.5)
    def analysis_resume(self, text: str) -> dict:
        # 截断过长文本，防止 token 超限和响应过慢
        text = text[:8000] if len(text) > 8000 else text
        prompt = f"""从以下简历文本提取信息，严格返回JSON（不要markdown包裹）：
            {{
                "name": "姓名",
                "age": int类型,
                "sex": "性别",
                "work_year": "工作年限",
                "skills": "技能(逗号分隔)",
                "self_evaluation": "自我评价",
                "job_intention": "求职意向",
                "education": [{{"school_name":"", "degree":"", "major":"", "start_date":"", "end_date":""}}],
                "projects": [{{"project_name":"", "description":"", "role":"", "start_date":"", "end_date":""}}]
            }}
            简历文本：{text}"""
        response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=90,
            )
        result = response.choices[0].message.content.strip()
        return extract_json_from_reply(result)
    
    @retry_on_failure(max_retries=3, delay=1.5)
    def get_user_image(self, text: str) -> str:
        """生成用户画像自然语言描述，用于与岗位画像做 embedding 相似度比对"""
        prompt = f"""根据以下候选人信息，用一段 100~200 字的自然语言描述其技术画像。
            要求：
            - 以"该候选人"开头
            - 综合描述其技术栈、工作年限、学历背景、项目领域、证书资质等
            - 语言连贯自然，像是招聘顾问在介绍一位候选人
            - 不要使用列表、JSON 或任何结构化格式，只输出纯文本段落
            - 不要加任何前缀说明或 markdown 包裹
            - 最多200字
            候选人信息：{text}"""
        response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=60,
            )
        return response.choices[0].message.content.strip()


    @retry_on_failure(max_retries=3, delay=1.5)
    def get_job_profile(self, description: str) -> str:
        """从岗位描述生成自然语言岗位画像，用于与用户画像做 embedding 相似度比对"""
        prompt = f"""根据以下岗位描述(JD)，用一段 100~200 字的自然语言概括该岗位画像。
            要求：
            - 以"该岗位"开头
            - 综合描述硬性要求、必备技术栈、工作年限、学历门槛、加分项等
            - 语言连贯自然，像是招聘顾问在介绍一个岗位
            - 不要使用列表、JSON 或任何结构化格式，只输出纯文本段落
            - 不要加任何前缀说明或 markdown 包裹
            岗位描述：{description}"""
        response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=60,
            )
        return response.choices[0].message.content.strip()


    

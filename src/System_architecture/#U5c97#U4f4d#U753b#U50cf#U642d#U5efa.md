# 岗位画像搭建

## 一、画像生成

### 数据来源

来自 **MySQL** `job_position` 表：

| 字段 | 用途 |
|------|------|
| `id` | 作为 Milvus 主键 `job_id` |
| `title` | 直接复制到 Milvus |
| `location` | 直接复制到 Milvus |
| `category` | 直接复制到 Milvus |
| `salary_min` + `salary_max` | 拼接为 `salary_range` 存入 Milvus |
| `description` | 交由 LLM 提取 `hard_requirements`、`priority_criteria`、画像摘要 `description` |

### 生成流程
```
[企业提交岗位信息]
      │
      ▼
 MySQL: job_position 入库
      │
      ▼
 读取 MySQL 字段 → 拼接提示词 → 调用大模型:

  输入: title + description + location + category + salary
  输出: hard_requirements（硬性要求）
        priority_criteria（加分项）
        description（画像摘要）
      │
      ▼
 拼接 Embedding 文本:
  title + location + category + salary_range + hard_requirements + priority_criteria + description
      │
      ▼
 Embedding → vector (1024维)
      │
      ▼
 Milvus: 写入 Collection `job_profile`
```

### Milvus `job_profile` 字段及来源

| 字段 | 类型 | 来源 |
|------|------|------|
| `job_id` | INT64 (PK) | **MySQL** `job_position.id` |
| `title` | VARCHAR(256) | **MySQL** `job_position.title` |
| `location` | VARCHAR(256) | **MySQL** `job_position.location` |
| `category` | VARCHAR(64) | **MySQL** `job_position.category` |
| `salary_range` | VARCHAR(128) | **MySQL** `salary_min` + `salary_max` 拼接 |
| `hard_requirements` | VARCHAR(4096) | **LLM** 从 `description` 提取 |
| `priority_criteria` | VARCHAR(4096) | **LLM** 从 `description` 提取 |
| `description` | VARCHAR(8192) | **LLM** 基于 `description` 总结 |
| `vector` | FLOAT_VECTOR(1024) | **Embedding** (上述字段拼接) |


## 二、画像匹配

### 匹配来源

来自 **MySQL** `resume` 表：

| 字段 | 用途 |
|------|------|
| `parsed_content`（TEXT） | LLM 解析简历后生成的人物画像文本 |

### 匹配流程
```
[候选人请求岗位匹配]
      │
      ▼
 读取 MySQL resume.parsed_content → 人物画像文本
      │
      ▼
 Embedding → 匹配向量 (1024维)
      │
      ▼
 Milvus.search(
   collection: job_profile,
   vector:     匹配向量,
   top_k:      N
 )
      │
      ▼
 Milvus 返回: [{job_id, score}, {job_id, score}, ...]   ← 仅 ID + 分数
      │
      ▼
 后端用 job_id 列表查 MySQL:
   SELECT * FROM job_position WHERE id IN (...)
   JOIN company ON job_position.company_id = company.id
      │
      ▼
 后端返回完整岗位列表 + 匹配分数，按 score 降序
```

### 前端渲染数据来源（全部来自 MySQL）

| 展示内容 | 数据来源 |
|----------|----------|
| 匹配度分数 | **后端组装**（Milvus `score` + MySQL 数据合并） |
| 岗位名称、薪资范围、地点、类别 | **MySQL** `job_position` |
| 学历要求、经验要求、招聘人数 | **MySQL** `job_position` |
| 企业名称、行业、规模 | **MySQL** `company`（JOIN `company_id`） |


## 三、画像更新

```
MySQL UPDATE job_position
      │
      ▼
 Milvus.delete(collection: job_profile, ids: [job_id])   ← 先删除旧画像
      │
      ▼
 重新读取 MySQL 字段 → LLM → Embedding
      │
      ▼
 Milvus.insert: 写入新画像 (job_id 不变)
```


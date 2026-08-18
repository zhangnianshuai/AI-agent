-- ============================================================
-- AI智能面试官与人才评估系统 - 数据库表设计
-- ============================================================

-- -----------------------------------------------------------
-- 1. 用户表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
    `id`            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '用户ID',
    `username`      VARCHAR(64)      NOT NULL                 COMMENT '用户名',
    `password_hash` VARCHAR(256)     NOT NULL                 COMMENT '密码哈希',
    `real_name`     VARCHAR(64)      DEFAULT NULL             COMMENT '真实姓名',
    `email`         VARCHAR(128)     DEFAULT NULL             COMMENT '邮箱',
    `phone`         VARCHAR(20)      DEFAULT NULL             COMMENT '手机号',
    `avatar_url`    VARCHAR(512)     DEFAULT NULL             COMMENT '头像地址',
    `role`          ENUM('candidate','hr','admin') NOT NULL   COMMENT '角色: candidate-候选人, hr-HR/老师, admin-管理员',
    `status`        TINYINT          NOT NULL DEFAULT 1       COMMENT '状态: 0-禁用, 1-启用',
    `created_at`    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email`    (`email`),
    KEY         `idx_role`   (`role`),
    KEY         `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- -----------------------------------------------------------
-- 2. 岗位表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `job_position`;
CREATE TABLE `job_position` (
    `id`                     BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '岗位ID',
    `company_id`             BIGINT UNSIGNED  NOT NULL                 COMMENT '所属企业ID',
    `agent_config_id`        BIGINT UNSIGNED  DEFAULT NULL             COMMENT '绑定的Agent配置ID',
    `question_bank_partition` VARCHAR(128)     DEFAULT NULL             COMMENT '题库分区名(同一公司不同岗位使用不同分区)',
    `title`                   VARCHAR(128)     NOT NULL                 COMMENT '岗位名称',
    `description`            TEXT             DEFAULT NULL             COMMENT '岗位描述和要求',
    `salary_min`             INT              DEFAULT NULL             COMMENT '薪资下限(单位:千)',
    `salary_max`             INT              DEFAULT NULL             COMMENT '薪资上限(单位:千)',
    `location`               VARCHAR(128)     DEFAULT NULL             COMMENT '工作地点',
    `category`               VARCHAR(64)      DEFAULT NULL             COMMENT '岗位分类',
    `education_requirement`  VARCHAR(64)      DEFAULT NULL             COMMENT '学历要求',
    `experience_requirement` VARCHAR(64)      DEFAULT NULL             COMMENT '经验要求',
    `headcount`              INT              DEFAULT 1                COMMENT '招聘人数',
    `status`                 TINYINT          NOT NULL DEFAULT 1       COMMENT '状态: 0-关闭, 1-开放',
    `created_at`             DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`             DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_company_id` (`company_id`),
    KEY `idx_category`  (`category`),
    KEY `idx_location`  (`location`),
    KEY `idx_status`    (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='岗位表';

-- -----------------------------------------------------------
-- 3. Agent面试官配置表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `agent_config`;
CREATE TABLE `agent_config` (
    `id`              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '配置ID',
    `model_name`      VARCHAR(64)      NOT NULL DEFAULT 'deepseek-v4-flash' COMMENT '使用的大模型',
    `temperature`     DECIMAL(3,2)     NOT NULL DEFAULT 0.70    COMMENT '模型温度',
    `max_tokens`      INT              NOT NULL DEFAULT 4096    COMMENT '最大输出token数',
    `system_prompt`   TEXT             DEFAULT NULL             COMMENT '系统提示词',
    `ranker_params`   INT              NOT NULL DEFAULT 5       COMMENT '每次回答参考题目数',
    `score_threshold` DECIMAL(3,2)     NOT NULL DEFAULT 0.70    COMMENT '检索相似度阈值',
    `question_nums`   INT              NOT NULL DEFAULT 10      COMMENT '最少问答题目数',
    `created_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent面试官配置表';
ALTER TABLE agent_config ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'interview';

-- -----------------------------------------------------------
-- 4. 公司企业表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `company`;
CREATE TABLE `company` (
    `id`             BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '公司ID',
    `name`           VARCHAR(256)     NOT NULL                 COMMENT '公司全称',
    `short_name`     VARCHAR(128)     DEFAULT NULL             COMMENT '公司简称',
    `milvus_db`                VARCHAR(128)     NOT NULL                 COMMENT 'Milvus数据库名(公司级数据隔离)',
    `question_bank_collection` VARCHAR(128)     DEFAULT NULL             COMMENT '公司题库Collection名(随机生成,所有岗位共用)',
    `industry`                 VARCHAR(64)      DEFAULT NULL             COMMENT '所属行业',
    `scale`          VARCHAR(32)      DEFAULT NULL             COMMENT '公司规模',
    `description`    TEXT             DEFAULT NULL             COMMENT '公司简介',
    `address`        VARCHAR(512)     DEFAULT NULL             COMMENT '公司地址',
    `website`        VARCHAR(256)     DEFAULT NULL             COMMENT '公司官网',
    `logo_url`       VARCHAR(512)     DEFAULT NULL             COMMENT 'Logo地址',
    `contact_person` VARCHAR(64)      DEFAULT NULL             COMMENT '联系人',
    `contact_phone`  VARCHAR(20)      DEFAULT NULL             COMMENT '联系电话',
    `status`         TINYINT          NOT NULL DEFAULT 1       COMMENT '状态: 0-禁用, 1-启用',
    `created_at`     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_name`    (`name`),
    KEY         `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司企业表';

-- -----------------------------------------------------------
-- 5. 简历表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `resume`;
CREATE TABLE `resume` (
    `id`              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '简历ID',
    `user_id`         BIGINT UNSIGNED  NOT NULL                 COMMENT '所属用户ID',
    `file_name`       VARCHAR(256)     NOT NULL                 COMMENT '原始文件名',
    `file_url`        VARCHAR(512)     NOT NULL                 COMMENT '文件存储地址',
    `parsed_content`  TEXT             DEFAULT NULL             COMMENT 'AI解析后生成人物画像',
    `name`            VARCHAR(64)      DEFAULT NULL             COMMENT '姓名',
    `age`             INT              DEFAULT NULL             COMMENT '年龄',
    `sex`             VARCHAR(16)      DEFAULT NULL             COMMENT '性别',
    `work_year`       VARCHAR(32)      DEFAULT NULL             COMMENT '工作年限',
    `skills`          TEXT             DEFAULT NULL             COMMENT '技能掌握',
    `self_evaluation` TEXT             DEFAULT NULL             COMMENT '自我评价',
    `job_intention`   VARCHAR(256)     DEFAULT NULL             COMMENT '求职意向',
    `is_default`      TINYINT          NOT NULL DEFAULT 0       COMMENT '是否默认简历: 0-否, 1-是',
    `status`          TINYINT          NOT NULL DEFAULT 1       COMMENT '状态: 0-删除, 1-正常',
    `created_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status`  (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='简历表';

-- -----------------------------------------------------------
-- 6. 个人项目表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `personal_project`;
CREATE TABLE `personal_project` (
    `id`           BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '项目ID',
    `resume_id`    BIGINT UNSIGNED  NOT NULL                 COMMENT '所属简历ID',
    `project_name` VARCHAR(256)     NOT NULL                 COMMENT '项目名称',
    `role`         VARCHAR(128)     DEFAULT NULL             COMMENT '担任角色',
    `description`  TEXT             DEFAULT NULL             COMMENT '项目描述',
    `technologies` JSON             DEFAULT NULL             COMMENT '使用技术栈',
    `start_date`   VARCHAR(32)      DEFAULT NULL             COMMENT '开始时间',
    `end_date`     VARCHAR(32)      DEFAULT NULL             COMMENT '结束时间',
    `achievements` TEXT             DEFAULT NULL             COMMENT '项目成果',
    `sort_order`   INT              NOT NULL DEFAULT 0       COMMENT '排序(越小越靠前)',
    `created_at`   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_resume_id` (`resume_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='个人项目表';

-- -----------------------------------------------------------
-- 7. 学历表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `education`;
CREATE TABLE `education` (
    `id`          BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '学历ID',
    `user_id`     BIGINT UNSIGNED  NOT NULL                 COMMENT '所属用户ID',
    `resume_id`   BIGINT UNSIGNED  NOT NULL                 COMMENT '来源简历ID',
    `school_name` VARCHAR(256)     DEFAULT NULL             COMMENT '学校名称',
    `major`       VARCHAR(256)     DEFAULT NULL             COMMENT '专业名称',
    `degree`      VARCHAR(64)      DEFAULT NULL             COMMENT '学历/学位',
    `start_date`  VARCHAR(32)      DEFAULT NULL             COMMENT '入学时间',
    `end_date`    VARCHAR(32)      DEFAULT NULL             COMMENT '毕业时间',
    `description` TEXT             DEFAULT NULL             COMMENT '在校经历/补充说明',
    `created_at`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id`   (`user_id`),
    KEY `idx_resume_id` (`resume_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学历表';

-- -----------------------------------------------------------
-- 8. 用户-企业表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `user_company`;
CREATE TABLE `user_company` (
    `id`         BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '关联ID',
    `user_id`    BIGINT UNSIGNED  NOT NULL                 COMMENT '用户ID',
    `company_id` BIGINT UNSIGNED  NOT NULL                 COMMENT '企业ID',
    `created_at` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_company` (`user_id`, `company_id`),
    KEY         `idx_company_id`  (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户-企业关联表';

-- -----------------------------------------------------------
-- 9. 面试会话表
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `interview_session`;
CREATE TABLE `interview_session` (
    `id`              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '会话ID',
    `user_id`         BIGINT UNSIGNED  NOT NULL                 COMMENT '候选人用户ID',
    `job_position_id` BIGINT UNSIGNED  NOT NULL                 COMMENT '面试岗位ID',
    `agent_config_id` BIGINT UNSIGNED  NOT NULL                 COMMENT '使用的Agent配置ID',
    `resume_id`       BIGINT UNSIGNED  DEFAULT NULL             COMMENT '关联简历ID',
    `company_id`      BIGINT UNSIGNED  DEFAULT NULL             COMMENT '所属企业ID',
    `status`          ENUM('pending','in_progress','completed','cancelled') NOT NULL DEFAULT 'pending' COMMENT '状态: pending-待开始, in_progress-进行中, completed-已完成, cancelled-已取消',
    `start_time`      DATETIME         DEFAULT NULL             COMMENT '开始时间',
    `end_time`        DATETIME         DEFAULT NULL             COMMENT '结束时间',
    `duration`        INT              DEFAULT NULL             COMMENT '面试时长(秒)',
    `created_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id`         (`user_id`),
    KEY `idx_job_position_id` (`job_position_id`),
    KEY `idx_resume_id`       (`resume_id`),
    KEY `idx_company_id`      (`company_id`),
    KEY `idx_status`          (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面试会话表';

-- -----------------------------------------------------------
-- 10. 面试记录表（一问一答明细）
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `interview_record`;
CREATE TABLE `interview_record` (
    `id`            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '记录ID',
    `session_id`    BIGINT UNSIGNED  NOT NULL                 COMMENT '所属面试会话ID',
    `round_number`  INT              NOT NULL DEFAULT 1       COMMENT '第几轮/题号',
    `question_type` VARCHAR(32)      DEFAULT NULL             COMMENT '题型: self_intro-自我介绍, project-项目深挖, technical-技术题, behavioral-行为题, qa-反问',
    `question`      TEXT             NOT NULL                 COMMENT '面试官提问内容',
    `answer`        TEXT             DEFAULT NULL             COMMENT '候选人回答内容',
    `score`         DECIMAL(5,2)     DEFAULT NULL             COMMENT '该题得分(0-100)',
    `comment`       TEXT             DEFAULT NULL             COMMENT 'AI对该回答的点评',
    `duration`      INT              DEFAULT NULL             COMMENT '该题耗时(秒)',
    `created_at`    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面试记录表（一问一答明细）';

-- -----------------------------------------------------------
-- 11. 面试评价表（一场面试的最终结果）
-- -----------------------------------------------------------
DROP TABLE IF EXISTS `interview_evaluation`;
CREATE TABLE `interview_evaluation` (
    `id`               BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT  COMMENT '评价ID',
    `session_id`       BIGINT UNSIGNED  NOT NULL                 COMMENT '面试会话ID',
    `total_score`      DECIMAL(5,2)     DEFAULT NULL             COMMENT '综合得分(0-100)',
    `summary`          TEXT             DEFAULT NULL             COMMENT '综合评价总结',
    `strengths`        TEXT             DEFAULT NULL             COMMENT '优势亮点',
    `weaknesses`       TEXT             DEFAULT NULL             COMMENT '不足之处',
    `suggestion`       TEXT             DEFAULT NULL             COMMENT '改进建议',
    `is_pass`          TINYINT          DEFAULT NULL             COMMENT '是否通过: 0-未通过, 1-通过',
    `created_at`       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_session`     (`session_id`),
    KEY         `idx_total_score` (`total_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面试评价表（一场面试的最终结果）';

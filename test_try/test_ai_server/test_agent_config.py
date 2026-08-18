"""对同一岗位测试 Agent 配置：创建 → 修改（以 job 绑定为准，幂等可重复运行）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.service.agent_server import AgentService
from server.models.agent import agent_config
from server.dao.job_dao import JobDAO

JOB_ID = 201969703491473408


def main():
    service = AgentService()
    job_dao = JobDAO()

    existing_id = job_dao.agent_config_id(JOB_ID)

    if existing_id is None:
        # ── 首次运行：创建 ──
        print("[首次] job 无绑定 → 创建新配置")
        config = agent_config()
        result = service.set_up_agent_config(JOB_ID, config)
        assert result.code == 200, f"创建失败: {result.message}"
        agent_id = result.data["agent_id"]
        print(f"  config.id: {config.id}")
        print(f"  agent_id:  {agent_id}")
        print(f"  action:    {result.data['action']}")
        assert result.data["action"] == "created"
    else:
        # ── 已有绑定，跳过创建 ──
        agent_id = existing_id
        print(f"[跳过] job 已有绑定 agent_id={agent_id}，无需重复创建")

    db_id = job_dao.agent_config_id(JOB_ID)
    assert db_id == agent_id, f"回写不一致: DB({db_id}) != result({agent_id})"
    print(f"  DB 验证:   {db_id}  [OK]")

    # ── 修改：在已有配置上改参数 ──
    print(f"\n[修改] 基于 agent_id={agent_id} 更新配置")
    config2 = agent_config(id=agent_id, temperature=0.90)
    print(f"  temperature: 0.70 → 0.90")

    result2 = service.set_up_agent_config(JOB_ID, config2)
    assert result2.code == 200, f"修改失败: {result2.message}"
    print(f"  agent_id:   {result2.data['agent_id']}")
    print(f"  action:     {result2.data['action']}")
    assert result2.data["action"] == "updated"
    assert result2.data["agent_id"] == agent_id, "修改后的 agent_id 应与创建时一致"

    db_id2 = job_dao.agent_config_id(JOB_ID)
    assert db_id2 == agent_id, f"回写不一致: DB({db_id2}) != result({agent_id})"
    print(f"  DB 验证:   {db_id2}  [OK]")

    print(f"\n{'=' * 40}")
    print("[OK] 全流程通过（幂等，不会产生重复 agent_config 记录）")


if __name__ == "__main__":
    main()

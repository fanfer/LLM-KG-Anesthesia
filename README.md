# 麻醉医生助手系统

一个基于LangChain和LangGraph的智能医疗对话系统，专注于麻醉术前评估和患者沟通。

## 功能特点

- 🏥 **多角色协作**：主治医生和专科医生无缝协作
- 📋 **信息采集**：智能提取和验证患者信息
- 📝 **病史记录**：系统化采集患者病史
- ⚠️ **风险评估**：全面的麻醉风险评估
- 🤝 **患者沟通**：通俗易懂的风险解释

## 项目结构

```
project/
├── main.py              # 主程序入口
├── Graph/               # 对话流程控制
│   ├── graph.py        # 对话图定义
│   ├── nodes.py        # 节点实现
│   ├── router.py       # 路由逻辑
│   └── state.py        # 状态管理
├── Chains/             # 对话链实现
│   ├── assistant2agent_chain.py    # 主助手链
│   ├── extract_info_chain.py       # 信息提取链
│   ├── history_chain.py           # 病史采集链
│   ├── information_chain.py       # 信息确认链
│   └── risk_chain.py             # 风险评估链
└── tests/              # 测试用例
```

## 许可证

MIT License

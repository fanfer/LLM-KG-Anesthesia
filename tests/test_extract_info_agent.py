import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import HumanMessage
from Graph.nodes import Extract_Info_Agent
from Graph.state import MedicalState

def test_extract_info_agent():
    # 构造测试数据
    messages = [
        HumanMessage(content="我叫张三"),
        HumanMessage(content="我今年45岁"),
        HumanMessage(content="我要做腹腔镜手术,用全麻")
    ]
    
    state = MedicalState({
        "messages": messages,
        "user_information": ""
    })
    
    # 创建mock的extract_info_chain
    mock_result = Mock()
    mock_result.name = "张三"
    mock_result.age = "45"
    mock_result.surgery = "腹腔镜手术"
    mock_result.anesthesia = "全麻"
    mock_result.additional_info = ""
    
    with patch("Graph.nodes.get_extract_info_chain") as mock_chain:
        mock_chain.return_value.invoke.return_value = mock_result
        
        # 调用被测试的函数
        result = Extract_Info_Agent(state)
        
        # 验证结果
        assert "user_information" in result
        assert "patient" in result
        assert result["patient"] == "张三"
        assert "姓名: 张三" in result["user_information"]
        assert "年龄: 45" in result["user_information"]
        assert "手术: 腹腔镜手术" in result["user_information"]
        assert "麻醉方式: 全麻" in result["user_information"]

def test_extract_info_agent_with_empty_messages():
    # 测试消息为空的情况
    state = MedicalState({
        "messages": [],
        "user_information": ""
    })
    
    with pytest.raises(IndexError):
        Extract_Info_Agent(state) 

test_extract_info_agent()
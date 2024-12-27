import os

from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_complete, gpt_4o_mini_complete

WORKING_DIR = "./dickens"

if not os.path.exists(WORKING_DIR):
    os.mkdir(WORKING_DIR)

rag = LightRAG(
    working_dir=WORKING_DIR,
    # llm_model_func=gpt_4o_mini_complete,
    llm_model_func=gpt_4o_complete,
    llm_model_kwargs={"base_url":os.environ.get("OPENAI_BASE_URL"), "api_key": os.environ.get("OPENAI_API_KEY")},
)


with open("./mz2.txt", "r", encoding="utf-8") as f:
    rag.insert(f.read())

# Perform hybrid search
print(
    rag.query("患者对头孢过敏，之前做过骨髓移植手术，现在需要进行心脏搭桥手术，进行全麻。请你进行风险评估，告知患者风险，并且给出麻醉方案。", param=QueryParam(mode="hybrid"))
)

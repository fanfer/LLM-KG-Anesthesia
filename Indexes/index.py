import os
import openai
from langchain.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings

openai.api_key = os.environ.get("OPENAI_API_KEY")
EMBEDDING_MODEL = OpenAIEmbeddings(openai_api_key=os.environ.get("OPENAI_API_KEY"))

AURA_CONNECTION_URI = os.environ.get('AURA_CONNECTION_URI')
AURA_USERNAME = os.environ.get('AURA_USERNAME')
AURA_PASSWORD = os.environ.get('AURA_PASSWORD')

def create_vector_index(label: str, index_name: str):
    return Neo4jVector.from_existing_graph(
        embedding=EMBEDDING_MODEL,
        url=AURA_CONNECTION_URI,
        username=AURA_USERNAME,
        password=AURA_PASSWORD,
        index_name=index_name,
        node_label=label,
        text_node_properties=['name'],
        embedding_node_property='embedding_vectors',
    )

#TODO: 修改成实际需要进行vector graph answer的indexes
def get_vector_index():
    return create_vector_index("Disease", "disease_vector")


from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel

model = LiteLLMModel(
    model_id="ollama_chat/qwen2:7b",
    api_base="http://127.0.0.1:11434",
    num_ctx=8192,
)

agent = CodeAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model
)

response = agent.run("ابحث عن آخر أخبار الذكاء الاصطناعي اليوم")
print(response)
import lmstudio as lms

model = lms.llm("qwen2.5-coder-3b-instruct-mlx")
result = model.respond("What is the meaning of life?")

print(result)

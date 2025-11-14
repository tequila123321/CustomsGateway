from dotenv import load_dotenv
load_dotenv()  # 加载 .env

from openai import OpenAI
client = OpenAI()  # 自动读取 OPENAI_API_KEY

print("API key 已加载，可以开始调用啦！")

# —— 真正的验证开始 ——
try:
    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",  # 用一个便宜的模型测试，省钱
        messages=[{"role": "user", "content": "地球半径是多大"}],
        max_tokens=50
    )
    answer = response.choices[0].message.content
    print("调用成功！OpenAI 回答：")
    print(answer)
except Exception as e:
    print("调用失败了！错误信息：")
    print(e)
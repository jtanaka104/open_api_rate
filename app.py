import streamlit as st
import requests
import json
from openai import OpenAI

# OpenAIクライアント初期化
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ツール（Function）定義
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "為替レートを取得するツール（USD→JPY）",
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "取得したい通貨コード（例：USD）"
                    }
                },
                "required": ["currency"]
            }
        }
    }
]

# MCPサーバー的なローカル処理関数
def get_exchange_rate(currency):
    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency}")
        data = response.json()
        return {"rate": data["rates"].get("JPY", "データなし")}
    except Exception as e:
        return {"rate": f"エラー: {str(e)}"}

# Streamlit UI
st.title("💱チャット with GPT-4o+MCP")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "あなたは為替情報に詳しいアシスタントです。"}
    ]

# ユーザー入力欄
user_input = st.chat_input("何か質問してみてください（例：1ドルはいくら？）")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    # LLMに送信（1ターン目）
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=st.session_state.messages,
        tools=tools,
        tool_choice="auto"
    )

    reply = response.choices[0].message
    tool_calls = getattr(reply, "tool_calls", None)

    if tool_calls:
        tool_call = tool_calls[0]
        func_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if func_name == "get_exchange_rate":
            tool_result = get_exchange_rate(**args)

            # assistant の tool_call 指示内容も content 付きで表示
            tool_call_msg = f"\n🔧 ツール呼び出し: `{func_name}`\n引数: `{tool_call.function.arguments}`"
            st.session_state.messages.append({
                "role": "assistant",
                "content": tool_call_msg,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                ]
            })

            # ツール応答も可視化して表示
            tool_content_str = json.dumps(tool_result, ensure_ascii=False)
            st.session_state.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": tool_content_str
            })

            # 最終応答（2ターン目）
            final_response = client.chat.completions.create(
                model="gpt-4o",
                messages=st.session_state.messages
            )
            reply = final_response.choices[0].message

    if reply.content:
        st.session_state.messages.append({"role": "assistant", "content": reply.content})

# チャット履歴を表示
for msg in st.session_state.messages:
    if msg["role"] in ["user", "assistant", "tool"] and msg.get("content"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

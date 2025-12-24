import asyncio
import os
import re
import json
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

API_URL = "http://localhost:11434/v1"
MODEL_NAME = "mistral-nemo"

class FakeToolCall:
    def __init__(self, name, args, call_id):
        self.id = call_id
        self.function = lambda: None
        self.function.name = name
        self.function.arguments = json.dumps(args) if isinstance(args, dict) else args

def parse_mistral_tools(content):
    if not content or "[TOOL_CALLS]" not in content:
        return None
    
    try:
        json_str = content.split("[TOOL_CALLS]")[1].strip()
        tools_data = json.loads(json_str)
        
        return [
            FakeToolCall(t['name'], t['arguments'], f"call_{i}") 
            for i, t in enumerate(tools_data)
        ]
    except Exception as e:
        print(f"Failed to parse Mistral tool string: {e}")
        return None

def clean_schema(schema):
    if isinstance(schema, dict):
        return {k: clean_schema(v) for k, v in schema.items() if k != "title"}
    elif isinstance(schema, list):
        return [clean_schema(v) for v in schema]
    else:
        return schema
    
def extract_code_from_markdown(content):
    if not content:
        return None
    pattern = r"```(?:\w+)?\s*\n([\s\S]*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return None

async def run():
    client = AsyncOpenAI(base_url=API_URL, api_key="dummy")
    
    server_params = StdioServerParameters(
        command="pdm", 
        args=["run", "python", "packages/pandas-analyst/src/server.py"],
        env=os.environ.copy()
    )

    async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        mcp_tools = await session.list_tools()
        
        openai_tools = [{
            "type": "function",
            "function": {
                "name": t.name, 
                "description": t.description, 
                "parameters": clean_schema(t.inputSchema)
            }
        } for t in mcp_tools.tools]
        
        print(f"Ready! Tools: {[t.name for t in mcp_tools.tools]}")
        messages = [{"role": "system", "content": """You are a Data Analyst. 
            Step 1: ALWAYS use `inspect_csv` first to check column names.
            Step 2: Write pandas code using `execute_pandas_code`.
            IMPORTANT: 
            - ALWAYS write complete, executable Python code. 
            - ALWAYS print() the final result.
            - NEVER modify file paths.
            EXAMPLES:
            User: "Calculate correlation between BTC and ETH close prices."
            Assistant: import pandas as pd
            df = pd.read_csv('data/real_crypto_2024.csv')
            btc = df[df['symbol']=='BTC']['Close'].reset_index(drop=True)
            eth = df[df['symbol']=='ETH']['Close'].reset_index(drop=True)
            corr = btc.corr(eth)
            print(f"Correlation Coefficient: {corr}")
            """}]

        while True:
            if (user_input := input("\nYou: ").strip()) == "exit": break
            messages.append({"role": "user", "content": user_input})

            try:
                response = await client.chat.completions.create(
                    model=MODEL_NAME, messages=messages, tools=openai_tools
                )
                msg = response.choices[0].message
                content = msg.content
                if not msg.tool_calls:
                    tool_calls = parse_mistral_tools(content)
                else:
                    tool_calls = msg.tool_calls
                
                if not tool_calls and content:
                    extracted_code = extract_code_from_markdown(content)
                    if extracted_code:
                        print("   (Detected Markdown code block. Auto-executing...)")
                        tool_calls = [FakeToolCall("execute_pandas_code", {"code": extracted_code}, "call_markdown")]

                if tool_calls:
                    if not tool_calls: 
                        messages.append({"role": "assistant", "content": content})
                    else:
                        messages.append(msg)

                    for tool in tool_calls:
                        print(f"Call: {tool.function.name}({tool.function.arguments})")
                        args = json.loads(tool.function.arguments)
                        if "filepath" in args:
                            args["filepath"] = args["filepath"].lstrip("/")
                            if not args["filepath"].startswith("data/"):
                                args["filepath"] = os.path.join("data", args["filepath"])
                        
                        if tool.function.name == "execute_pandas_code":
                            print(f"Code:\n{args.get('code')}")

                        result = await session.call_tool(tool.function.name, arguments=args)
                        result_text = result.content[0].text
                        print(f"Output: {result_text[:200]}..." if len(result_text)>200 else f"Output: {result_text}")
                        messages.append({"role": "tool", "tool_call_id": tool.id, "content": result.content[0].text})
                
                    final_res = await client.chat.completions.create(model=MODEL_NAME, messages=messages)
                    print(f"\nAgent: {final_res.choices[0].message.content}")
                    messages.append(final_res.choices[0].message)
                else:
                    print(f"\nAgent: {msg.content}")

            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
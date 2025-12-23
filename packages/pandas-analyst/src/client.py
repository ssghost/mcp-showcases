import asyncio
import os
import json
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

API_URL = "http://localhost:11234/v1"
MODEL_NAME = "gemma-3-4b"

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
                "parameters": t.inputSchema
            }
        } for t in mcp_tools.tools]
        
        print(f"Ready! Tools: {[t.name for t in mcp_tools.tools]}")
        messages = [{"role": "system", "content": "You are a Data Analyst using local tools."}]

        while True:
            if (user_input := input("\n👤 You: ").strip()) == "exit": break
            messages.append({"role": "user", "content": user_input})

            response = await client.chat.completions.create(
                model=MODEL_NAME, messages=messages, tools=openai_tools
            )
            msg = response.choices[0].message
            messages.append(msg)

            if msg.tool_calls:
                for tool in msg.tool_calls:
                    print(f"Call: {tool.function.name}({tool.function.arguments})")
                    result = await session.call_tool(tool.function.name, arguments=json.loads(tool.function.arguments))
                    messages.append({"role": "tool", "tool_call_id": tool.id, "content": result.content[0].text})
                
                final_res = await client.chat.completions.create(model=MODEL_NAME, messages=messages)
                print(f"\nAgent: {final_res.choices[0].message.content}")
                messages.append(final_res.choices[0].message)
            else:
                print(f"\nAgent: {msg.content}")

if __name__ == "__main__":
    asyncio.run(run())
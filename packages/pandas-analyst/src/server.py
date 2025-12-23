from mcp.server.fastmcp import FastMCP
import pandas as pd
import io
import sys
import traceback

mcp = FastMCP("Pandas Analyst")

@mcp.tool()
def inspect_csv(filepath: str) -> str:
    try:
        df = pd.read_csv(filepath)
        buffer = io.StringIO()
        df.info(buf=buffer)
        info_str = buffer.getvalue()
        preview = df.head().to_markdown(index=False)
        return f"--- DATA INFO ---\n{info_str}\n\n--- FIRST 5 ROWS ---\n{preview}"
    except Exception as e:
        return f"Error reading CSV: {str(e)}"

@mcp.tool()
def execute_pandas_code(code: str) -> str:
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    
    try:
        local_scope = {"pd": pd}
        exec(code, {}, local_scope)
        result = redirected_output.getvalue()
        if not result:
            return "Code executed successfully but printed no output. Did you forget to 'print()' the result?"
        return result
    except Exception as e:
        return f"Execution Error:\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout

if __name__ == "__main__":
    mcp.run()
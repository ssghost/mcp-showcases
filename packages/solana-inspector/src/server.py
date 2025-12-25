from mcp.server.fastmcp import FastMCP
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts

mcp = FastMCP("Solana Inspector")
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
solana_client = Client(SOLANA_RPC_URL, timeout=30.0)

KNOWN_TOKENS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "Bonk",
}

@mcp.tool()
def get_balance(wallet_address: str) -> str:
    print(f"Checking balance for: {wallet_address}")
    try:
        pubkey = Pubkey.from_string(wallet_address)
        response = solana_client.get_balance(pubkey)
        
        lamports = response.value
        sol_balance = lamports / 1_000_000_000
        
        return f"{sol_balance:.4f} SOL"

    except ValueError:
        return "Error: Invalid wallet address format."
    except Exception as e:
        return f"Error: Failed to fetch from Solana. Details: {str(e)}."
    
@mcp.tool()
def get_token_holdings(wallet_address: str) -> str:
    try:
        pubkey = Pubkey.from_string(wallet_address)
        opts = TokenAccountOpts(
            program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
            encoding="jsonParsed"
        )
        response = solana_client.get_token_accounts_by_owner_json_parsed(pubkey, opts)
        raw_accounts = response.value
        holdings = []
        for account in raw_accounts:
            data = account.account.data.parsed['info']
            mint = data['mint']
            ui_amount = data['tokenAmount']['uiAmount']
            
            if ui_amount and ui_amount > 0:
                token_name = KNOWN_TOKENS.get(mint, f"Unknown ({mint[:4]}...)")
                holdings.append(f"- {token_name}: {ui_amount:,.2f}")

        if not holdings:
            return "\nRESULT: No positive balance tokens found."
        return "\nRESULT: \n" + "\n".join(holdings)

    except Exception as e:
        return f"\nCRITICAL ERROR: {repr(e)}."

@mcp.tool()
def get_recent_transactions(wallet_address: str, limit: int = 5) -> str:
    print(f"Fetching transactions for: {wallet_address}")
    try:
        pubkey = Pubkey.from_string(wallet_address)
        response = solana_client.get_signatures_for_address(pubkey, limit=limit)
        transactions = []

        for idx, tx in enumerate(response.value):
            status = "Success" if tx.err is None else f"Failed ({tx.err})"
            
            transactions.append(
                f"{idx+1}. Signature: {str(tx.signature)[:15]}... \n"
                f"Status: {status}\n"
                f"Slot: {tx.slot}"
            )
            
        if not transactions:
            return "No recent transactions found."
            
        return f"Last {limit} Transactions:\n" + "\n".join(transactions)

    except Exception as e:
        return f"Error fetching transactions: {str(e)}."

if __name__ == "__main__":
    mcp.run()
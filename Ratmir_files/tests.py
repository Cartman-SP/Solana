import asyncio
from axiomtradeapi import AxiomTradeClient

class TokenSniperBot:
    def __init__(self):
        self.client = AxiomTradeClient(
            auth_token="your-auth-token",
            refresh_token="your-refresh-token"
        )
        self.min_market_cap = 5.0     # Minimum 5 SOL market cap
        self.min_liquidity = 10.0     # Minimum 10 SOL liquidity
        
    async def handle_new_tokens(self, tokens):
        for token in tokens:
            # Basic token info
            token_name = token.get('tokenName', 'Unknown')
            market_cap = token.get('marketCapSol', 0)
            liquidity = token.get('liquiditySol', 0)
            
            # Check if token meets our criteria
            if (market_cap >= self.min_market_cap and 
                liquidity >= self.min_liquidity):
                
                print(f"🎯 QUALIFIED TOKEN: {token_name}")
                print(f"   Market Cap: {market_cap:.2f} SOL")
                print(f"   Liquidity: {liquidity:.2f} SOL")
                
                await self.analyze_token_opportunity(token)
    
    async def start_monitoring(self):
        await self.client.subscribe_new_tokens(self.handle_new_tokens)
        await self.client.ws.start()
from fastmcp.server.auth import JWTVerifier, AccessToken

class DebugJWTVerifier(JWTVerifier):
    async def verify_token(self, token: str):
        print("\n=== RAW TOKEN ===")
        print(token)

        result = await super().verify_token(token)

        print("\n=== VERIFIED TOKEN ===")
        print(result)

        return result
def require_scope(ctx, scope: str):
    if not ctx or not ctx.auth:
        raise Exception("Unauthorized")

    scopes = getattr(ctx.auth, "scopes", [])

    if scope not in scopes:
        raise Exception(f"Forbidden: missing scope '{scope}'")

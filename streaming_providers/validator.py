from typing import Dict, Any

from db.schemas import UserData
from streaming_providers.mapper import VALIDATE_CREDENTIALS_FUNCTIONS
from utils.network import get_user_public_ip
from fastapi import Request


async def validate_provider_credentials(
    request: Request, user_data: UserData
) -> Dict[str, Any]:
    """
    Validate streaming provider credentials.
    
    Checks if the provider is supported and validates credentials
    by calling the provider-specific validation function.
    
    Args:
        request: FastAPI request object (for IP detection)
        user_data: User configuration data containing provider credentials
        
    Returns:
        Dictionary with "status" ("success" or "error") and optional "message"
        
    Example:
        {"status": "success"} or {"status": "error", "message": "Invalid API key"}
    """
    if not user_data.streaming_provider:
        return {"status": "success"}

    if user_data.streaming_provider.service not in VALIDATE_CREDENTIALS_FUNCTIONS:
        return {
            "status": "error",
            "message": f"Provider {user_data.streaming_provider.service} is not supported.",
        }

    user_ip = await get_user_public_ip(request, user_data)
    return await VALIDATE_CREDENTIALS_FUNCTIONS[user_data.streaming_provider.service](
        user_data=user_data, user_ip=user_ip
    )

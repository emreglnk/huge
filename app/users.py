from typing import Optional

from .db import db
from .models import User, UserInDB
from .security import get_password_hash

async def get_user(username: str) -> Optional[UserInDB]:
    """Retrieves a user from the database by their username."""
    user_doc = await db.users.find_one({"username": username})
    if user_doc:
        return UserInDB(**user_doc)
    return None

async def create_user(user: User) -> UserInDB:
    """Creates a new user in the database."""
    hashed_password = get_password_hash(user.password)
    user_in_db = UserInDB(**user.dict(), hashed_password=hashed_password)
    
    await db.users.insert_one(user_in_db.dict())
    return user_in_db

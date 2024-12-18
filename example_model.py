from pydantic import BaseModel, Field
from typing import Optional

class UserModel(BaseModel):
    id: int = Field(gt=0, description="User ID must be positive")
    name: str = Field(min_length=2, max_length=50)
    email: str
    age: Optional[int] = Field(None, ge=0, le=120)
    
# Example usage
user = UserModel(
    id=1,
    name="John Doe",
    email="john@example.com",
    age=30
)

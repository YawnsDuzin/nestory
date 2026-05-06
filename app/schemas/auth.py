from pydantic import BaseModel, EmailStr, Field


class SignupForm(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginForm(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

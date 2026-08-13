from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str
    invite_code: Optional[str] = None

class TokenRefresh(BaseModel):
    refresh_token: str

class AuthUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    company_id: uuid.UUID
    company_name: str

class AuthCompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserResponse

class RegisterResponse(BaseModel):
    user: AuthUserResponse
    company: AuthCompanyResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    access_token: str
    new_password: str

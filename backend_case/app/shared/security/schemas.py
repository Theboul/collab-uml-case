"""
Esquemas Pydantic v2 para contratos de Autenticación y Cuentas de Usuario.
"""

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    fullName: str = Field(
        min_length=2,
        max_length=150,
        validation_alias=AliasChoices("fullName", "full_name"),
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    credential: str = Field(
        min_length=10,
        validation_alias=AliasChoices("credential", "id_token"),
    )


class UserDto(BaseModel):
    id: str
    email: str
    fullName: str
    avatarUrl: str | None = None


class AuthResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int = 900
    user: UserDto


class UserProfileResponse(BaseModel):
    id: str
    email: str
    fullName: str
    avatarUrl: str | None = None
    identities: list[str]
    isVerified: bool

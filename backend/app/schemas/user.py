from pydantic import BaseModel, field_validator


class UpdateProfileRequest(BaseModel):
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SetApiKeyRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        if not v.startswith("sk-ant-"):
            raise ValueError("Anthropic API keys must start with 'sk-ant-'")
        return v


class DeleteAccountRequest(BaseModel):
    password: str

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=3, max_length=20)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    userId: int
    email: str
    nickname: str
    roleName: str = "user"


class ProfileResponse(BaseModel):
    userId: int
    email: str
    nickname: str
    roleName: str
    bioText: str
    ageCategory: str
    favoriteColors: List[str]
    themeMode: str
    languageCode: str
    notificationsEnabled: bool


class UpdateProfileBody(BaseModel):
    nickname: str = Field(min_length=3, max_length=20)
    bioText: str = Field(default="", max_length=500)
    ageCategory: str
    favoriteColors: List[str] = []


class PostCommentBody(BaseModel):
    commentText: str = Field(min_length=5, max_length=1000)


class ProjectBody(BaseModel):
    projectName: str = Field(min_length=3, max_length=80)
    categoryName: str
    deadlineDate: Optional[str] = ""
    descriptionText: Optional[str] = ""


class ProjectStepBody(BaseModel):
    stepDescription: str = Field(min_length=3, max_length=1000)


class StepPatchBody(BaseModel):
    isCompleted: bool


class MixtureBody(BaseModel):
    mixtureName: str = Field(min_length=3, max_length=100)
    resultHex: str
    totalWeight: float
    recipeItems: list
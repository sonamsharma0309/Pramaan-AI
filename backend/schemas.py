from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    org: str = Field(default="", max_length=120)
    role: Literal["patient", "biller"] = "patient"
    invite_code: str = Field(default="", max_length=24)

    @field_validator("name", "org")
    @classmethod
    def strip(cls, v):
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
    portal: Optional[Literal["patient", "biller", "admin"]] = None
    totp_code: str = Field(default="", max_length=8)


class GoogleIn(BaseModel):
    credential: str
    role: Literal["patient", "biller"] = "patient"
    portal: Optional[Literal["patient", "biller"]] = None


class EligibilityIn(BaseModel):
    payer: str = Field(default="", max_length=80)
    denial_code: str = Field(default="", max_length=10)
    procedure: str = Field(default="", max_length=200)
    amount: float = Field(default=0, ge=0)
    days_since_denial: int = Field(default=30, ge=0, le=3650)
    has_records: bool = False


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    org: Optional[str] = Field(default=None, max_length=120)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class ClaimIn(BaseModel):
    claim_no: str = Field(min_length=1, max_length=40)
    patient_name: str = Field(min_length=1, max_length=80)
    payer: str = Field(min_length=1, max_length=80)
    procedure_code: str = Field(default="", max_length=20)
    procedure_desc: str = Field(default="", max_length=200)
    diagnosis: str = Field(default="", max_length=200)
    billed_amount: float = Field(default=0, ge=0)
    denied_amount: Optional[float] = Field(default=None, ge=0)
    denial_code: str = Field(default="", max_length=10)
    denial_reason: str = Field(default="", max_length=400)
    service_date: str = Field(default="", max_length=20)
    denied_on: str = Field(default="", max_length=20)
    ehr_notes: str = Field(default="", max_length=60000)


class ClaimPatch(BaseModel):
    patient_name: Optional[str] = None
    payer: Optional[str] = None
    procedure_code: Optional[str] = None
    procedure_desc: Optional[str] = None
    diagnosis: Optional[str] = None
    billed_amount: Optional[float] = None
    denied_amount: Optional[float] = None
    denial_code: Optional[str] = None
    denial_reason: Optional[str] = None
    service_date: Optional[str] = None
    denied_on: Optional[str] = None
    ehr_notes: Optional[str] = Field(default=None, max_length=60000)
    status: Optional[str] = None


class PolicyIn(BaseModel):
    payer: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=160)
    content: str = Field(min_length=20, max_length=200000)


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    payer: str = ""


class AppealPatch(BaseModel):
    letter: Optional[str] = Field(default=None, max_length=30000)
    status: Optional[str] = None
    outcome: Optional[str] = None
    recovered_amount: Optional[float] = Field(default=None, ge=0)


class TotpIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TokenIn(BaseModel):
    token: str


class ThemeIn(BaseModel):
    theme: Literal["light", "dark"]


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    kind: Literal["general", "partner", "demo", "support"] = "general"
    message: str = Field(min_length=10, max_length=4000)


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)


class FhirImportIn(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9\-.]{1,64}$")

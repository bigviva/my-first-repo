"""Pydantic request models."""
from typing import Optional

from pydantic import BaseModel, Field


class UserIn(BaseModel):
    name: str
    email: str
    department: str = ""
    role: str = Field("quality", pattern="^(admin|quality|viewer|supplier)$")
    password: str = ""
    supplier_name: str = ""


class UserAdminUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|quality|viewer|supplier)$")
    active: Optional[bool] = None
    supplier_name: Optional[str] = None
    password: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class EscapeIn(BaseModel):
    title: str
    description: str = ""
    escape_type: str = Field("internal", pattern="^(internal|external)$")
    customer: str = ""
    program: str = ""
    part_number: str = ""
    severity: int = Field(3, ge=1, le=4)
    likelihood: int = Field(2, ge=1, le=4)
    containment_plan: str = ""
    containment_due: Optional[str] = None
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class EscapeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    customer: Optional[str] = None
    program: Optional[str] = None
    part_number: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=4)
    likelihood: Optional[int] = Field(None, ge=1, le=4)
    containment_plan: Optional[str] = None
    containment_due: Optional[str] = None
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class StatusChange(BaseModel):
    status: str
    note: str = ""
    changed_by: str = "system"


class CarIn(BaseModel):
    title: str
    description: str = ""
    car_type: str = Field("internal", pattern="^(internal|external)$")
    supplier: str = ""
    escape_id: Optional[int] = None
    severity: int = Field(3, ge=1, le=4)
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class CarUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    supplier: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=4)
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class CarValidation(BaseModel):
    validated_by: Optional[int] = None
    validation_notes: str = ""
    approved: bool = True


class CarResponse(BaseModel):
    response_text: str


class CarDecision(BaseModel):
    accept: bool
    notes: str = ""


class CapaIn(BaseModel):
    title: str
    description: str = ""
    car_id: Optional[int] = None
    rcca_method: str = "5-Why"
    root_cause_category: str = ""
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class CapaUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    rcca_method: Optional[str] = None
    root_cause_category: Optional[str] = None
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


class CapaVerification(BaseModel):
    effective: bool
    effectiveness_result: str = ""
    verified_by: Optional[int] = None


class BulletinIn(BaseModel):
    title: str
    body: str = ""
    car_id: Optional[int] = None
    audience: str = "All Quality"
    issued_by: Optional[int] = None


class NotificationIn(BaseModel):
    recipient: str
    message: str

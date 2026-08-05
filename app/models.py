"""Pydantic request models."""
from pydantic import BaseModel, Field


class UserIn(BaseModel):
    name: str
    email: str
    department: str = ""


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
    containment_due: str | None = None
    due_date: str | None = None
    owner_id: int | None = None


class EscapeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    customer: str | None = None
    program: str | None = None
    part_number: str | None = None
    severity: int | None = Field(None, ge=1, le=4)
    likelihood: int | None = Field(None, ge=1, le=4)
    containment_plan: str | None = None
    containment_due: str | None = None
    due_date: str | None = None
    owner_id: int | None = None


class StatusChange(BaseModel):
    status: str
    note: str = ""
    changed_by: str = "system"


class CarIn(BaseModel):
    title: str
    description: str = ""
    car_type: str = Field("internal", pattern="^(internal|external)$")
    supplier: str = ""
    escape_id: int | None = None
    severity: int = Field(3, ge=1, le=4)
    due_date: str | None = None
    owner_id: int | None = None


class CarUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    supplier: str | None = None
    severity: int | None = Field(None, ge=1, le=4)
    due_date: str | None = None
    owner_id: int | None = None


class CarValidation(BaseModel):
    validated_by: int | None = None
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
    car_id: int | None = None
    rcca_method: str = "5-Why"
    root_cause_category: str = ""
    due_date: str | None = None
    owner_id: int | None = None


class CapaUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    rcca_method: str | None = None
    root_cause_category: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    due_date: str | None = None
    owner_id: int | None = None


class CapaVerification(BaseModel):
    effective: bool
    effectiveness_result: str = ""
    verified_by: int | None = None


class BulletinIn(BaseModel):
    title: str
    body: str = ""
    car_id: int | None = None
    audience: str = "All Quality"
    issued_by: int | None = None


class NotificationIn(BaseModel):
    recipient: str
    message: str

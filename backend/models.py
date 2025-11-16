from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional
from datetime import datetime
from enum import Enum
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserType(str, Enum):
    ADMIN = "admin"
    CLIENT = "client"
    EMPLOYEE = "employee"

class SubscriptionPlan(str, Enum):
    TRIAL = "trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str
    website: str
    mobile: Optional[str] = None
    business_type: Optional[str] = None
    location: Optional[str] = None
    pan: Optional[str] = None
    tan: Optional[str] = None

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('passwords do not match')
        return v

    @validator('mobile')
    def validate_mobile(cls, v):
        if v and not v.startswith('+'):
            if not v.isdigit() or len(v) < 10:
                raise ValueError('Invalid mobile number format')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class QuestionAnswer(BaseModel):
    question: str
    answer: str
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime

class Client(BaseModel):
    name: str
    email: EmailStr
    website: str
    mobile: Optional[str]
    business_type: Optional[str]
    location: Optional[str]
    pan: Optional[str]
    tan: Optional[str]
    subscription_plan: SubscriptionPlan = SubscriptionPlan.TRIAL
    subscription_start: datetime
    subscription_end: datetime
    questions_allowed: int = 5
    questions_used: int = 0
    modifications_allowed: int = 0
    modifications_used: int = 0
    is_active: bool = True
    created_at: datetime

class Employee(BaseModel):
    name: str
    email: EmailStr
    mobile: Optional[str]
    client_id: str
    website: str
    is_active: bool = True
    created_at: datetime

class Admin(BaseModel):
    name: str
    email: EmailStr
    mobile: Optional[str]
    is_active: bool = True
    created_at: datetime

class Subscription(BaseModel):
    client_id: str
    plan: SubscriptionPlan
    amount: float
    razorpay_payment_id: str
    razorpay_order_id: str
    start_date: datetime
    end_date: datetime
    status: str = "active"
    created_at: datetime

class Log(BaseModel):
    action: str
    user_id: str
    user_type: UserType
    client_id: Optional[str]
    details: dict
    timestamp: datetime

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class EmployeeCreateRequest(BaseModel):
    name: str
    email: EmailStr
    website: str

class SubscriptionCreateRequest(BaseModel):
    plan: SubscriptionPlan
    website: str

class QuestionRequestType(str, Enum):
    MODIFY = "modify"
    DELETE = "delete" 
    ADD = "add"

class QuestionRequest(BaseModel):
    client_id: str
    request_type: QuestionRequestType
    question_number: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected
    admin_notes: Optional[str] = None
    created_by: str
    created_by_type: str
    created_at: datetime
    updated_at: datetime

class Notification(BaseModel):
    user_id: str
    user_type: UserType
    title: str
    message: str
    type: str  # question_request, system, etc.
    data: dict
    is_read: bool = False
    created_at: datetime

# Add these new models to your existing models.py

class UserQuestion(BaseModel):
    client_id: str
    website: str
    question: str
    answer: Optional[str] = None
    is_valid: bool = False
    ask_count: int = 0
    is_approved: bool = False
    requested_by_client: bool = False
    created_at: datetime
    updated_at: datetime

class QuestionRequest(BaseModel):
    client_id: str
    website: str
    question: str
    answer: Optional[str] = None
    request_type: str  # 'add', 'modify', 'delete'
    status: str = 'pending'  # 'pending', 'approved', 'rejected'
    admin_notes: Optional[str] = None
    original_question_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class QuestionStats(BaseModel):
    client_id: str
    website: str
    question: str
    valid_ask_count: int = 0
    requested_ask_count: int = 0
    last_asked: Optional[datetime] = None
from fastapi import FastAPI, HTTPException, Depends, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer, util
import numpy as np
from datetime import datetime, timedelta
import razorpay
import os
import random
from dotenv import load_dotenv
from bson import ObjectId
from database import db
from models import *
from auth import *
from fastapi.responses import FileResponse
import base64
from email_service import email_service, get_welcome_email_template, get_password_reset_email_template, get_employee_credentials_email_template
import secrets
import string
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from gtts import gTTS
import tempfile, os
from googletrans import Translator
load_dotenv()

app = FastAPI(title="SpeechBot", version="1.0.0")

# Dynamic CORS origins - will be updated with client websites
cors_origins = [
    "https://pavankalyanande47.github.io",
    "http://localhost:3000",
    "https://adminorbit.batalks.in",
    "https://fidgetingly-testable-christoper.ngrok-free.dev",
    "*"  # For testing, remove in production
]

def get_cors_origins():
    """Get dynamic CORS origins including client websites"""
    try:
        clients_collection = db.get_collection("clients")
        clients = clients_collection.find({}, {"website": 1})
        
        dynamic_origins = cors_origins.copy()
        for client in clients:
            website = client.get("website", "").strip()
            if website:
                # Add both http and https versions
                if not website.startswith(('http://', 'https://')):
                    dynamic_origins.append(f"https://{website}")
                    dynamic_origins.append(f"http://{website}")
                else:
                    dynamic_origins.append(website)
        
        return list(set(dynamic_origins))  # Remove duplicates
    except Exception as e:
        print(f"Error loading CORS origins: {e}")
        return cors_origins

# CORS middleware with dynamic origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/translate")
async def translate_text(translation_data: dict):
    text = translation_data.get("text")
    source_lang = translation_data.get("source_lang", "en")
    target_lang = translation_data.get("target_lang", "te")
    
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        translator = Translator()
        translation = translator.translate(text, src=source_lang, dest=target_lang)
        return {"translated_text": translation.text}
        
    except Exception as e:
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail="Translation failed")

@app.post("/tts")
async def tts(request: Request):
    data = await request.json()
    text = data.get("text", "")
    lang = data.get("lang", "en")
    lang_code = "te" if lang == "te" else "en"
    tts = gTTS(text=text, lang=lang_code, slow=False)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp.name)
    return FileResponse(tmp.name, media_type="audio/mpeg")

@app.get("/speechbot.js")
def serve_speechbot_js():
    js_path = os.path.join(os.path.dirname(__file__), "..", "speechbot", "speechbot.js")
    abs_path = os.path.abspath(js_path)
    return FileResponse(
        abs_path,
        media_type="application/javascript",
        headers={"Access-Control-Allow-Origin": "*"}
    )

# Initialize models
model = SentenceTransformer('all-MiniLM-L6-v2')

# Razorpay setup
razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
)

# Helper function to get plan limits
def get_plan_limits(plan):
    """Get the limits for each subscription plan"""
    plan_limits = {
        "trial": {
            "questions_allowed": 5,
            "modifications_allowed": 0,
            "allow_edits": False,
            "allow_deletes": False,
            "duration_days": 2
        },
        "monthly": {
            "questions_allowed": 50,
            "modifications_allowed": 10,
            "allow_edits": True,
            "allow_deletes": True,
            "duration_days": 30
        },
        "quarterly": {
            "questions_allowed": 150,
            "modifications_allowed": 30,
            "allow_edits": True,
            "allow_deletes": True,
            "duration_days": 90
        },
        "yearly": {
            "questions_allowed": 500,
            "modifications_allowed": 100,
            "allow_edits": True,
            "allow_deletes": True,
            "duration_days": 365
        }
    }
    return plan_limits.get(plan, plan_limits["trial"])

# Centralized function to update client subscription
def update_client_subscription(client_id: str, new_plan: str, is_new_subscription: bool = False):
    """
    Update client subscription with all related fields
    """
    clients_collection = db.get_collection("clients")
    
    try:
        # Get current client data
        client = clients_collection.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get new plan limits
        plan_limits = get_plan_limits(new_plan)
        
        # Prepare update data
        update_data = {
            "subscription_plan": new_plan,
            "questions_allowed": plan_limits["questions_allowed"],
            "modifications_allowed": plan_limits["modifications_allowed"],
            "allow_edits": plan_limits["allow_edits"],
            "allow_deletes": plan_limits["allow_deletes"]
        }
        
        # Handle subscription dates
        current_time = datetime.utcnow()
        if is_new_subscription or new_plan == "trial":
            update_data["subscription_start"] = current_time
            update_data["subscription_end"] = current_time + timedelta(days=plan_limits["duration_days"])
        else:
            current_end = client.get("subscription_end", current_time)
            if current_end < current_time:
                update_data["subscription_start"] = current_time
                update_data["subscription_end"] = current_time + timedelta(days=plan_limits["duration_days"])
            else:
                update_data["subscription_start"] = client.get("subscription_start", current_time)
                update_data["subscription_end"] = current_end + timedelta(days=plan_limits["duration_days"])
        
        # Reset usage counters when changing from trial to paid plan
        if client.get("subscription_plan") == "trial" and new_plan != "trial":
            update_data["questions_used"] = 0
            update_data["modifications_used"] = 0
        
        # Apply the update
        result = clients_collection.update_one(
            {"_id": ObjectId(client_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            print(f"Warning: No documents were updated for client {client_id}")
        
        # Return the updated subscription data
        updated_client = clients_collection.find_one({"_id": ObjectId(client_id)})
        return updated_client
        
    except Exception as e:
        print(f"Error updating client subscription: {str(e)}")
        raise

# Function to sync subscription limits for all clients
def sync_all_clients_subscriptions():
    """Sync subscription limits for all clients based on their current plan"""
    clients_collection = db.get_collection("clients")
    
    try:
        clients = clients_collection.find({})
        synced_count = 0
        
        for client in clients:
            current_plan = client.get("subscription_plan", "trial")
            plan_limits = get_plan_limits(current_plan)
            
            # Check if limits need to be updated
            needs_update = (
                client.get("questions_allowed") != plan_limits["questions_allowed"] or
                client.get("modifications_allowed") != plan_limits["modifications_allowed"] or
                client.get("allow_edits") != plan_limits["allow_edits"] or
                client.get("allow_deletes") != plan_limits["allow_deletes"]
            )
            
            if needs_update:
                update_data = {
                    "questions_allowed": plan_limits["questions_allowed"],
                    "modifications_allowed": plan_limits["modifications_allowed"],
                    "allow_edits": plan_limits["allow_edits"],
                    "allow_deletes": plan_limits["allow_deletes"]
                }
                
                clients_collection.update_one(
                    {"_id": client["_id"]},
                    {"$set": update_data}
                )
                synced_count += 1
                print(f"Synced subscription limits for client: {client.get('email')}")
        
        print(f"Subscription sync completed. Updated {synced_count} clients.")
        return synced_count
        
    except Exception as e:
        print(f"Error syncing all client subscriptions: {str(e)}")
        return 0

# Add startup event to create default admin and update CORS
@app.on_event("startup")
async def startup_event():
    admins_collection = db.get_collection("admins")
    
    # Create default admin if none exists
    default_admin = {
        "name": "System Admin",
        "email": "admin@speechbot.com", 
        "password": get_password_hash("admin123"),
        "mobile": "+911111111111",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    if not admins_collection.find_one({"email": "admin@speechbot.com"}):
        admins_collection.insert_one(default_admin)
        print("✅ Created default admin: admin@speechbot.com / admin123")
    else:
        print("✅ Default admin already exists")
    
    # Sync all client subscriptions on startup
    print("🔄 Syncing all client subscriptions...")
    synced_count = sync_all_clients_subscriptions()
    print(f"✅ Synced {synced_count} client subscriptions")
    
    # Update CORS origins with client websites
    print("🔄 Updating CORS origins with client websites...")

# Dependency to get current user
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Authorization header missing"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format"
        )
    
    token = authorization.split(" ")[1]
    if not token:
        raise HTTPException(
            status_code=401, 
            detail="Token missing"
        )
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired token"
        )
    
    user_type = payload.get("user_type")
    user_id = payload.get("user_id")
    
    if not user_type or not user_id:
        raise HTTPException(
            status_code=401, 
            detail="Invalid token payload"
        )
    
    try:
        if user_type == "admin":
            user = db.get_collection("admins").find_one({"_id": ObjectId(user_id)})
        elif user_type == "client":
            user = db.get_collection("clients").find_one({"_id": ObjectId(user_id)})
        elif user_type == "employee":
            user = db.get_collection("employees").find_one({"_id": ObjectId(user_id)})
        else:
            raise HTTPException(status_code=401, detail="Invalid user type")
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Convert ObjectId to string for JSON serialization
        user["_id"] = str(user["_id"])
        if user_type == "employee" and "client_id" in user:
            user["client_id"] = str(user["client_id"])
            
        return {**user, "user_type": user_type}
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"User lookup failed: {str(e)}") 

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))

# Auth endpoints
@app.post("/signup")
async def signup(signup_data: SignupRequest):
    clients_collection = db.get_collection("clients")
    
    # Check if email already exists
    if clients_collection.find_one({"email": signup_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if website already exists for this email
    if clients_collection.find_one({"email": signup_data.email, "website": signup_data.website}):
        raise HTTPException(status_code=400, detail="Website already registered for this email")
    
    # Check if mobile already exists (if provided)
    if signup_data.mobile and clients_collection.find_one({"mobile": signup_data.mobile}):
        raise HTTPException(status_code=400, detail="Mobile number already registered")
    
    # Create client using centralized subscription function
    client_data = {
        "name": signup_data.name,
        "email": signup_data.email,
        "password": get_password_hash(signup_data.password),
        "website": signup_data.website,
        "mobile": signup_data.mobile,
        "business_type": signup_data.business_type,
        "location": signup_data.location,
        "pan": signup_data.pan,
        "tan": signup_data.tan,
        "subscription_plan": "trial",
        "questions_used": 0,
        "modifications_used": 0,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    result = clients_collection.insert_one(client_data)
    client_id = str(result.inserted_id)
    
    # Use centralized function to set up trial subscription
    update_client_subscription(client_id, "trial", is_new_subscription=True)
    
    # Send welcome email
    email_body = get_welcome_email_template(signup_data.name, signup_data.website)
    email_service.send_email(
        signup_data.email,
        "Welcome to SpeechBot!",
        email_body,
        is_html=True
    )
    
    # Create log
    log_entry = {
        "action": "client_signup",
        "user_id": client_id,
        "user_type": "client",
        "client_id": client_id,
        "details": {"website": signup_data.website, "mobile": signup_data.mobile},
        "timestamp": datetime.utcnow()
    }
    db.get_collection("logs").insert_one(log_entry)
    
    return {"message": "Signup successful. Welcome email sent!", "client_id": client_id}

@app.post("/forgot-password")
async def forgot_password(forgot_data: ForgotPasswordRequest):
    clients_collection = db.get_collection("clients")
    employees_collection = db.get_collection("employees")
    admins_collection = db.get_collection("admins")
    
    # Check in all collections
    user = None
    user_type = None
    name = None
    
    # Check clients
    client = clients_collection.find_one({"email": forgot_data.email})
    if client:
        user = client
        user_type = "client"
        name = client["name"]
    
    # Check employees
    if not user:
        employee = employees_collection.find_one({"email": forgot_data.email})
        if employee:
            user = employee
            user_type = "employee"
            name = employee["name"]
    
    # Check admins
    if not user:
        admin = admins_collection.find_one({"email": forgot_data.email})
        if admin:
            user = admin
            user_type = "admin"
            name = admin["name"]
    
    if not user:
        # Don't reveal that email doesn't exist for security
        return {"message": "If the email exists, a password reset OTP has been sent"}
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP in database (expires in 10 minutes)
    otp_entry = {
        "email": forgot_data.email,
        "otp": otp,
        "purpose": "password_reset",
        "verified": False,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }
    
    db.get_collection("password_reset_otps").insert_one(otp_entry)
    
    # Send password reset email
    email_body = get_password_reset_email_template(name, otp)
    email_service.send_email(
        forgot_data.email,
        "Password Reset OTP - SpeechBot",
        email_body,
        is_html=True
    )
    
    return {"message": "Password reset OTP sent to your email"}

@app.post("/reset-password")
async def reset_password(reset_data: ResetPasswordRequest):
    otp_collection = db.get_collection("password_reset_otps")
    clients_collection = db.get_collection("clients")
    employees_collection = db.get_collection("employees")
    admins_collection = db.get_collection("admins")
    
    # Find the most recent OTP for this email
    otp_record = otp_collection.find_one(
        {"email": reset_data.email, "purpose": "password_reset", "verified": False},
        sort=[("created_at", -1)]
    )
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="No password reset request found")
    
    # Check if OTP is expired
    if datetime.utcnow() > otp_record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP has expired")
    
    # Verify OTP
    if otp_record["otp"] != reset_data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Mark OTP as verified
    otp_collection.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"verified": True}}
    )
    
    # Update password in the appropriate collection
    hashed_password = get_password_hash(reset_data.new_password)
    
    # Try to update in clients
    result = clients_collection.update_one(
        {"email": reset_data.email},
        {"$set": {"password": hashed_password}}
    )
    
    # If not in clients, try employees
    if result.modified_count == 0:
        result = employees_collection.update_one(
            {"email": reset_data.email},
            {"$set": {"password": hashed_password}}
        )
    
    # If not in employees, try admins
    if result.modified_count == 0:
        result = admins_collection.update_one(
            {"email": reset_data.email},
            {"$set": {"password": hashed_password}}
        )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Password reset successfully"}

#Login route
@app.post("/login")
async def login(login_data: LoginRequest):
    # Check in clients
    client = db.get_collection("clients").find_one({"email": login_data.email})
    if client and verify_password(login_data.password, client["password"]):
        token = create_access_token(
            data={"user_id": str(client["_id"]), "user_type": "client"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": token, "token_type": "bearer", "user_type": "client"}
    
    # Check in employees
    employee = db.get_collection("employees").find_one({"email": login_data.email})
    if employee and verify_password(login_data.password, employee["password"]):
        token = create_access_token(
            data={"user_id": str(employee["_id"]), "user_type": "employee"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": token, "token_type": "bearer", "user_type": "employee"}
    
    # Check in admins
    admin = db.get_collection("admins").find_one({"email": login_data.email})
    if admin and verify_password(login_data.password, admin["password"]):
        token = create_access_token(
            data={"user_id": str(admin["_id"]), "user_type": "admin"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": token, "token_type": "bearer", "user_type": "admin"}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

# User profile endpoints
@app.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    try:
        profile_data = {
            "name": current_user.get("name", ""),
            "email": current_user.get("email", ""),
            "mobile": current_user.get("mobile", ""),
            "website": current_user.get("website", ""),
            "business_type": current_user.get("business_type", ""),
            "location": current_user.get("location", ""),
            "pan": current_user.get("pan", ""),
            "tan": current_user.get("tan", ""),
            "user_type": current_user.get("user_type", "")
        }
        return profile_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")

@app.put("/profile")
async def update_profile(profile_data: dict, current_user: dict = Depends(get_current_user)):
    try:
        user_type = current_user["user_type"]
        collection_name = "clients" if user_type == "client" else "employees" if user_type == "employee" else "admins"
        
        update_data = {}
        if "name" in profile_data:
            update_data["name"] = profile_data["name"]
        if "mobile" in profile_data:
            update_data["mobile"] = profile_data["mobile"]
        if "website" in profile_data and user_type == "client":
            update_data["website"] = profile_data["website"]
        if "business_type" in profile_data and user_type == "client":
            update_data["business_type"] = profile_data["business_type"]
        if "location" in profile_data and user_type == "client":
            update_data["location"] = profile_data["location"]
        if "pan" in profile_data and user_type == "client":
            update_data["pan"] = profile_data["pan"]
        if "tan" in profile_data and user_type == "client":
            update_data["tan"] = profile_data["tan"]
        
        if update_data:
            db.get_collection(collection_name).update_one(
                {"_id": ObjectId(current_user["_id"])},
                {"$set": update_data}
            )
        
        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

# Employee management endpoints
@app.post("/employees")
async def create_employee(employee_data: EmployeeCreateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] not in ["admin", "client"]:
        raise HTTPException(status_code=403, detail="Not authorized to create employees")
    
    employees_collection = db.get_collection("employees")
    clients_collection = db.get_collection("clients")
    
    try:
        # Check if email already exists
        if employees_collection.find_one({"email": employee_data.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Determine client_id and verify website
        if current_user["user_type"] == "admin":
            # For admin, they need to specify client_id in request or find by website
            client = clients_collection.find_one({"website": employee_data.website})
            if not client:
                raise HTTPException(status_code=400, detail="No client found for this website")
            client_id = str(client["_id"])
        else:  # client
            # Verify that the client owns this website
            client = clients_collection.find_one({"_id": ObjectId(current_user["_id"]), "website": employee_data.website})
            if not client:
                raise HTTPException(status_code=400, detail="You don't have access to this website")
            client_id = current_user["_id"]
        
        # Generate random password
        random_password = generate_random_password()
        
        # Create employee
        employee_entry = {
            "name": employee_data.name,
            "email": employee_data.email,
            "mobile": employee_data.get("mobile"),
            "password": get_password_hash(random_password),
            "client_id": client_id,
            "website": employee_data.website,
            "is_active": True,
            "created_by": str(current_user["_id"]),
            "created_at": datetime.utcnow()
        }
        
        result = employees_collection.insert_one(employee_entry)
        
        # Send credentials email to employee
        admin_name = current_user.get("name", "Administrator")
        email_body = get_employee_credentials_email_template(
            employee_data.name,
            employee_data.email,
            random_password,
            employee_data.website,
            admin_name
        )
        email_service.send_email(
            employee_data.email,
            "Your SpeechBot Account Credentials",
            email_body,
            is_html=True
        )
        
        # Create log
        log_entry = {
            "action": "create_employee",
            "user_id": str(current_user["_id"]),
            "user_type": current_user["user_type"],
            "client_id": str(client_id),
            "details": {"employee_id": str(result.inserted_id), "employee_email": employee_data.email},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Employee created successfully. Credentials sent via email.", "employee_id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating employee: {str(e)}")

@app.get("/employees")
async def get_employees(current_user: dict = Depends(get_current_user)):
    employees_collection = db.get_collection("employees")
    
    try:
        if current_user["user_type"] == "admin":
            employees = list(employees_collection.find())
        else:  # client
            employees = list(employees_collection.find({"client_id": str(current_user["_id"])}))
        
        for emp in employees:
            emp["_id"] = str(emp["_id"])
            emp["client_id"] = str(emp["client_id"])
            # Remove password from response
            if "password" in emp:
                del emp["password"]
        
        return employees
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching employees: {str(e)}")

@app.put("/employees/{employee_id}")
async def update_employee(employee_id: str, employee_data: dict, current_user: dict = Depends(get_current_user)):
    employees_collection = db.get_collection("employees")
    
    try:
        employee = employees_collection.find_one({"_id": ObjectId(employee_id)})
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check permissions
        if current_user["user_type"] == "client" and employee["client_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to update this employee")
        
        update_data = {}
        if "name" in employee_data:
            update_data["name"] = employee_data["name"]
        if "email" in employee_data:
            update_data["email"] = employee_data["email"]
        if "mobile" in employee_data:
            update_data["mobile"] = employee_data["mobile"]
        if "password" in employee_data and employee_data["password"]:
            update_data["password"] = get_password_hash(employee_data["password"])
        if "is_active" in employee_data:
            update_data["is_active"] = employee_data["is_active"]
        
        if update_data:
            employees_collection.update_one(
                {"_id": ObjectId(employee_id)},
                {"$set": update_data}
            )
        
        # Create log
        log_entry = {
            "action": "update_employee",
            "user_id": str(current_user["_id"]),
            "user_type": current_user["user_type"],
            "client_id": employee["client_id"],
            "details": {"employee_id": employee_id},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Employee updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating employee: {str(e)}")

@app.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str, current_user: dict = Depends(get_current_user)):
    employees_collection = db.get_collection("employees")
    
    try:
        employee = employees_collection.find_one({"_id": ObjectId(employee_id)})
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check permissions
        if current_user["user_type"] == "client" and employee["client_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to delete this employee")
        
        employees_collection.delete_one({"_id": ObjectId(employee_id)})
        
        # Create log
        log_entry = {
            "action": "delete_employee",
            "user_id": str(current_user["_id"]),
            "user_type": current_user["user_type"],
            "client_id": employee["client_id"],
            "details": {"employee_id": employee_id},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Employee deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting employee: {str(e)}")

# Admin Question Management endpoints
@app.post("/admin/questions")
async def admin_add_question(question_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    questions_collection = db.get_collection("questions")
    
    try:
        client_id = question_data.get("client_id")
        if not client_id:
            raise HTTPException(status_code=400, detail="Client ID is required")
        
        client = clients_collection.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Enhanced subscription check
        if datetime.utcnow() > client["subscription_end"]:
            raise HTTPException(
                status_code=400, 
                detail="Client subscription expired. Please renew subscription to add questions."
            )
        
        # Get current plan limits
        current_plan = client.get("subscription_plan", "trial")
        plan_limits = get_plan_limits(current_plan)
        
        current_questions_allowed = plan_limits["questions_allowed"]
        current_questions_used = client.get("questions_used", 0)
        
        if current_questions_used >= current_questions_allowed:
            raise HTTPException(
                status_code=400, 
                detail=f"Question limit reached for client's {current_plan} plan. "
                       f"Used {current_questions_used}/{current_questions_allowed} questions."
            )
        
        # Add question
        question_entry = {
            "client_id": client_id,
            "website": client["website"],
            "question": question_data["question"],
            "answer": question_data["answer"],
            "created_by": str(current_user["_id"]),
            "created_at": datetime.utcnow(),
            "updated_by": str(current_user["_id"]),
            "updated_at": datetime.utcnow()
        }
        
        result = questions_collection.insert_one(question_entry)
        
        # Update client question count
        clients_collection.update_one(
            {"_id": ObjectId(client_id)},
            {"$inc": {"questions_used": 1}}
        )
        
        # Create log
        log_entry = {
            "action": "admin_add_question",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": str(client_id),
            "details": {"question_id": str(result.inserted_id)},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Question added successfully for client"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding question: {str(e)}")

@app.put("/admin/questions/{question_id}")
async def admin_update_question(question_id: str, question_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    questions_collection = db.get_collection("questions")
    clients_collection = db.get_collection("clients")
    
    try:
        question = questions_collection.find_one({"_id": ObjectId(question_id)})
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Get client to check current subscription status
        client = clients_collection.find_one({"_id": ObjectId(question["client_id"])})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Enhanced subscription check
        if datetime.utcnow() > client["subscription_end"]:
            raise HTTPException(
                status_code=400, 
                detail="Client subscription expired. Please renew subscription to modify questions."
            )
        
        # Check if edits are allowed for this plan
        if not client.get("allow_edits", False):
            raise HTTPException(
                status_code=400, 
                detail="Question edits are not allowed in client's current plan. "
                       "Client needs to upgrade to a paid plan."
            )
        
        # Check modification limits for paid plans
        current_modifications_allowed = client.get("modifications_allowed", 0)
        current_modifications_used = client.get("modifications_used", 0)
        
        if current_modifications_used >= current_modifications_allowed:
            raise HTTPException(
                status_code=400, 
                detail=f"Modification limit reached for client's {client.get('subscription_plan', 'trial')} plan. "
                       f"Used {current_modifications_used}/{current_modifications_allowed} modifications."
            )
        
        update_data = {
            "question": question_data["question"],
            "answer": question_data["answer"],
            "updated_by": str(current_user["_id"]),
            "updated_at": datetime.utcnow()
        }
        
        questions_collection.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": update_data}
        )
        
        # Increment modifications count for paid plans
        clients_collection.update_one(
            {"_id": ObjectId(question["client_id"])},
            {"$inc": {"modifications_used": 1}}
        )
        
        # Create log
        log_entry = {
            "action": "admin_update_question",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": question["client_id"],
            "details": {"question_id": question_id},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Question updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating question: {str(e)}")

@app.delete("/admin/questions/{question_id}")
async def admin_delete_question(question_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    questions_collection = db.get_collection("questions")
    clients_collection = db.get_collection("clients")
    
    try:
        # Validate the question_id format
        if not ObjectId.is_valid(question_id):
            raise HTTPException(status_code=400, detail="Invalid question ID format")
        
        question = questions_collection.find_one({"_id": ObjectId(question_id)})
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Get client to check subscription status
        client = clients_collection.find_one({"_id": ObjectId(question["client_id"])})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Enhanced subscription check
        if datetime.utcnow() > client["subscription_end"]:
            raise HTTPException(
                status_code=400, 
                detail="Client subscription expired. Please renew subscription to delete questions."
            )
        
        # Check if deletes are allowed for this plan
        if not client.get("allow_deletes", False):
            raise HTTPException(
                status_code=400, 
                detail="Question deletions are not allowed in client's current plan. "
                       "Client needs to upgrade to a paid plan."
            )
        
        # Check modification limits for paid plans (deletions count as modifications)
        current_modifications_allowed = client.get("modifications_allowed", 0)
        current_modifications_used = client.get("modifications_used", 0)
        
        if current_modifications_used >= current_modifications_allowed:
            raise HTTPException(
                status_code=400, 
                detail=f"Modification limit reached for client's {client.get('subscription_plan', 'trial')} plan. "
                       f"Used {current_modifications_used}/{current_modifications_allowed} modifications."
            )
        
        # Delete the question
        delete_result = questions_collection.delete_one({"_id": ObjectId(question_id)})
        
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Question not found or already deleted")
        
        # Update client question count and modification count
        clients_collection.update_one(
            {"_id": ObjectId(question["client_id"])},
            {
                "$inc": {
                    "questions_used": -1,
                    "modifications_used": 1
                }
            }
        )
        
        # Create log
        log_entry = {
            "action": "admin_delete_question",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": question["client_id"],
            "details": {"question_id": question_id},
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Question deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting question: {str(e)}")

# Client can only view questions (no add/edit/delete)
@app.get("/questions")
async def get_questions(current_user: dict = Depends(get_current_user)):
    questions_collection = db.get_collection("questions")
    
    try:
        if current_user["user_type"] == "admin":
            questions = list(questions_collection.find())
        elif current_user["user_type"] == "client":
            questions = list(questions_collection.find({"client_id": str(current_user["_id"])}))
        else:  # employee
            questions = list(questions_collection.find({"client_id": current_user["client_id"]}))
        
        for q in questions:
            q["_id"] = str(q["_id"])
            q["client_id"] = str(q["client_id"])
        
        return questions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching questions: {str(e)}")

# Enhanced Speech bot endpoint with better subscription checking
@app.post("/speechbot/query")
async def speechbot_query(query_data: dict):
    website = query_data.get("website")
    question = query_data.get("question")
    language = query_data.get("language", "en")  # Get language parameter
    
    print(f"Query received - Website: {website}, Language: {language}, Question: {question}")
    
    if not website or not question:
        raise HTTPException(status_code=400, detail="Website and question are required")
    
    clients_collection = db.get_collection("clients")
    questions_collection = db.get_collection("questions")
    
    client = clients_collection.find_one({"website": website})
    if not client:
        return {"answer": "Client not found"}
    
    # Enhanced subscription check
    current_time = datetime.utcnow()
    subscription_end = client.get("subscription_end", current_time)
    
    if current_time > subscription_end:
        return {"answer": "Subscription expired. Please renew your subscription to use SpeechBot."}
    
    # Check if client is active
    if not client.get("is_active", True):
        return {"answer": "Account is inactive. Please contact support."}
    
    # Get all questions for this client
    client_questions = list(questions_collection.find({"client_id": str(client["_id"])}))
    
    if not client_questions:
        return {"answer": "I don't have answers configured yet. Please contact the website administrator."}
    
    # Use sentence transformers to find best match
    questions_text = [q["question"] for q in client_questions]
    answers = [q["answer"] for q in client_questions]
    
    # Encode questions and query
    question_embeddings = model.encode(questions_text)
    query_embedding = model.encode([question])
    
    # Calculate similarities
    similarities = util.cos_sim(query_embedding, question_embeddings)[0]
    best_match_idx = similarities.argmax().item()
    best_similarity = similarities[best_match_idx].item()
    
    # Threshold for considering it a match
    if best_similarity > 0.6:
        return {"answer": answers[best_match_idx]}
    else:
        return {"answer": "I'm sorry, I don't have an answer for that question. Please ask something else."}
# Subscription endpoints
@app.post("/subscription/create-order")
async def create_subscription_order(subscription_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "client":
        raise HTTPException(status_code=403, detail="Only clients can create subscriptions")
    
    plan = subscription_data.get("plan")
    website = subscription_data.get("website")
    
    if not website:
        raise HTTPException(status_code=400, detail="Website is required for subscription")
    
    # Verify client owns this website or it's new
    clients_collection = db.get_collection("clients")
    existing_client = clients_collection.find_one({
        "_id": ObjectId(current_user["_id"]),
        "website": website
    })
    
    if not existing_client:
        # Check if website already exists for other clients
        website_exists = clients_collection.find_one({"website": website})
        if website_exists:
            raise HTTPException(status_code=400, detail="Website already registered by another client")
    
    amount_map = {
        "monthly": 50000,  # in paise
        "quarterly": 180000,
        "yearly": 500000
    }
    
    amount = amount_map.get(plan)
    
    if not amount:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    try:
        order_data = {
            "amount": amount,
            "currency": "INR",
            "receipt": f"subscription_{current_user['_id']}_{website}",
            "notes": {
                "plan": plan,
                "client_id": str(current_user["_id"]),
                "website": website
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        return order
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment order creation failed: {str(e)}")

# Enhanced subscription verification to update plan limits using centralized function
@app.post("/subscription/verify")
async def verify_subscription(verification_data: dict, current_user: dict = Depends(get_current_user)):
    clients_collection = db.get_collection("clients")
    subscriptions_collection = db.get_collection("subscriptions")
    
    try:
        params_dict = {
            'razorpay_order_id': verification_data['razorpay_order_id'],
            'razorpay_payment_id': verification_data['razorpay_payment_id'],
            'razorpay_signature': verification_data['razorpay_signature']
        }
        
        # Verify payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Update client subscription using centralized function
        plan = verification_data.get("plan")
        amount_map = {
            "monthly": 50000,
            "quarterly": 180000,
            "yearly": 500000
        }
        
        amount = amount_map.get(plan, 0)
        
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan")
        
        # Use centralized function to update subscription
        updated_client = update_client_subscription(
            client_id=str(current_user["_id"]),
            new_plan=plan,
            is_new_subscription=True
        )
        
        # Create subscription record
        subscription = {
            "client_id": str(current_user["_id"]),
            "plan": plan,
            "amount": amount,
            "razorpay_payment_id": verification_data["razorpay_payment_id"],
            "razorpay_order_id": verification_data["razorpay_order_id"],
            "start_date": updated_client["subscription_start"],
            "end_date": updated_client["subscription_end"],
            "created_at": datetime.utcnow()
        }
        subscriptions_collection.insert_one(subscription)
        
        # Create log
        log_entry = {
            "action": "subscription_created",
            "user_id": str(current_user["_id"]),
            "user_type": current_user["user_type"],
            "client_id": str(current_user["_id"]),
            "details": {
                "plan": plan, 
                "amount": amount,
                "payment_id": verification_data["razorpay_payment_id"]
            },
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Subscription activated successfully"}
    
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Payment verification failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment verification error: {str(e)}")

# Enhanced endpoint to get client's current subscription status
@app.get("/subscription/status")
async def get_subscription_status(current_user: dict = Depends(get_current_user)):
    clients_collection = db.get_collection("clients")
    
    try:
        client = clients_collection.find_one({"_id": ObjectId(current_user["_id"])})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        current_time = datetime.utcnow()
        subscription_end = client.get("subscription_end", current_time)
        is_expired = current_time > subscription_end
        
        # Get current plan limits
        current_plan = client.get("subscription_plan", "trial")
        plan_limits = get_plan_limits(current_plan)
        
        # Use plan limits instead of stored values
        questions_allowed = plan_limits["questions_allowed"]
        questions_used = client.get("questions_used", 0)
        modifications_allowed = plan_limits["modifications_allowed"]
        modifications_used = client.get("modifications_used", 0)
        allow_edits = plan_limits["allow_edits"]
        allow_deletes = plan_limits["allow_deletes"]
        
        subscription_status = {
            "plan": current_plan,
            "start_date": client.get("subscription_start"),
            "end_date": subscription_end,
            "questions_allowed": questions_allowed,
            "questions_used": questions_used,
            "questions_remaining": questions_allowed - questions_used,
            "modifications_allowed": modifications_allowed,
            "modifications_used": modifications_used,
            "modifications_remaining": modifications_allowed - modifications_used,
            "allow_edits": allow_edits,
            "allow_deletes": allow_deletes,
            "website": client.get("website", ""),
            "is_active": client.get("is_active", True),
            "is_trial": current_plan == "trial",
            "is_expired": is_expired,
            "days_remaining": max(0, (subscription_end - current_time).days) if not is_expired else 0
        }
        
        return subscription_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subscription status: {str(e)}")

# Add a new endpoint to sync subscription limits
@app.post("/admin/clients/{client_id}/sync-limits")
async def sync_client_limits(client_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    
    try:
        client = clients_collection.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        current_plan = client.get("subscription_plan", "trial")
        plan_limits = get_plan_limits(current_plan)
        
        # Update client with correct limits
        update_data = {
            "questions_allowed": plan_limits["questions_allowed"],
            "modifications_allowed": plan_limits["modifications_allowed"],
            "allow_edits": plan_limits["allow_edits"],
            "allow_deletes": plan_limits["allow_deletes"]
        }
        
        clients_collection.update_one(
            {"_id": ObjectId(client_id)},
            {"$set": update_data}
        )
        
        # Create log
        log_entry = {
            "action": "sync_client_limits",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": client_id,
            "details": {
                "previous_limits": {
                    "questions_allowed": client.get("questions_allowed"),
                    "modifications_allowed": client.get("modifications_allowed")
                },
                "new_limits": update_data
            },
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {
            "message": "Client limits synced successfully",
            "plan": current_plan,
            "new_limits": update_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing client limits: {str(e)}")

# Add endpoint to get available plans
@app.get("/subscription/plans")
async def get_subscription_plans():
    plans = [
        {
            "id": "monthly",
            "name": "Monthly",
            "price": 500,
            "price_paise": 50000,
            "questions_allowed": 50,
            "modifications_allowed": 10,
            "description": "Perfect for small businesses",
            "features": ["50 questions/month", "10 modifications", "Edit & Delete questions"]
        },
        {
            "id": "quarterly",
            "name": "Quarterly",
            "price": 1800,
            "price_paise": 180000,
            "questions_allowed": 150,
            "modifications_allowed": 30,
            "description": "Great value for growing businesses",
            "savings": "Save 10%",
            "features": ["150 questions/quarter", "30 modifications", "Edit & Delete questions", "Priority support"]
        },
        {
            "id": "yearly",
            "name": "Yearly",
            "price": 5000,
            "price_paise": 500000,
            "questions_allowed": 500,
            "modifications_allowed": 100,
            "description": "Best value for established businesses",
            "savings": "Save 17%",
            "features": ["500 questions/year", "100 modifications", "Edit & Delete questions", "Priority support", "Advanced analytics"]
        }
    ]
    return plans

@app.get("/subscription/payment/{payment_id}")
async def get_payment_details(payment_id: str, current_user: dict = Depends(get_current_user)):
    try:
        payment = razorpay_client.payment.fetch(payment_id)
        return payment
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payment details: {str(e)}")

# Admin endpoints
@app.get("/admin/clients")
async def get_all_clients(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    clients = list(clients_collection.find())
    
    for client in clients:
        client["_id"] = str(client["_id"])
        # Remove password from response
        if "password" in client:
            del client["password"]
    
    return clients

@app.get("/admin/employees")
async def get_all_employees(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    employees_collection = db.get_collection("employees")
    employees = list(employees_collection.find())
    
    for employee in employees:
        employee["_id"] = str(employee["_id"])
        # Remove password from response
        if "password" in employee:
            del employee["password"]
    
    return employees

@app.get("/admin/questions")
async def get_all_questions(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    questions_collection = db.get_collection("questions")
    questions = list(questions_collection.find())
    
    for question in questions:
        question["_id"] = str(question["_id"])
    
    return questions

@app.get("/admin/subscriptions")
async def get_all_subscriptions(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    subscriptions_collection = db.get_collection("subscriptions")
    subscriptions = list(subscriptions_collection.find())
    
    for subscription in subscriptions:
        subscription["_id"] = str(subscription["_id"])
    
    return subscriptions

@app.get("/admin/logs")
async def get_system_logs(limit: int = 100, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logs_collection = db.get_collection("logs")
    logs = list(logs_collection.find().sort("timestamp", -1).limit(limit))
    
    for log in logs:
        log["_id"] = str(log["_id"])
    
    return logs

@app.delete("/admin/clients/{client_id}")
async def delete_client(client_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    questions_collection = db.get_collection("questions")
    employees_collection = db.get_collection("employees")
    
    # Delete client - Convert string to ObjectId
    result = clients_collection.delete_one({"_id": ObjectId(client_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Delete client's questions
    questions_collection.delete_many({"client_id": client_id})
    
    # Delete client's employees  
    employees_collection.delete_many({"client_id": client_id})
    
    return {"message": "Client and all associated data deleted successfully"}

@app.delete("/admin/employees/{employee_id}")
async def delete_employee(employee_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    employees_collection = db.get_collection("employees")
    
    result = employees_collection.delete_one({"_id": ObjectId(employee_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return {"message": "Employee deleted successfully"}

@app.get("/admin/clients-search")
async def search_clients(query: str = "", current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    
    try:
        search_filter = {}
        if query:
            search_filter = {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}},
                    {"website": {"$regex": query, "$options": "i"}},
                    {"mobile": {"$regex": query, "$options": "i"}}
                ]
            }
        
        clients = list(clients_collection.find(search_filter).limit(50))
        
        for client in clients:
            client["_id"] = str(client["_id"])
            # Remove password from response
            if "password" in client:
                del client["password"]
        
        return clients
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching clients: {str(e)}")

# Enhanced Admin endpoint to update client subscription manually using centralized function
@app.put("/admin/clients/{client_id}/subscription")
async def update_client_subscription(client_id: str, subscription_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    
    try:
        client = clients_collection.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Update subscription data using centralized function
        if "subscription_plan" in subscription_data:
            new_plan = subscription_data["subscription_plan"]
            
            # Use centralized function to update subscription
            updated_client = update_client_subscription(
                client_id=client_id,
                new_plan=new_plan,
                is_new_subscription=False
            )
        
        # Handle manual overrides (optional)
        update_data = {}
        if "questions_allowed" in subscription_data:
            update_data["questions_allowed"] = subscription_data["questions_allowed"]
        
        if "modifications_allowed" in subscription_data:
            update_data["modifications_allowed"] = subscription_data["modifications_allowed"]
        
        if "questions_used" in subscription_data:
            update_data["questions_used"] = subscription_data["questions_used"]
        
        if "modifications_used" in subscription_data:
            update_data["modifications_used"] = subscription_data["modifications_used"]
        
        if "is_active" in subscription_data:
            update_data["is_active"] = subscription_data["is_active"]
        
        # Apply manual overrides if any
        if update_data:
            clients_collection.update_one(
                {"_id": ObjectId(client_id)},
                {"$set": update_data}
            )
        
        # Create log
        log_entry = {
            "action": "admin_subscription_update",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": client_id,
            "details": {
                **update_data,
                "previous_plan": client.get("subscription_plan"),
                "new_plan": subscription_data.get("subscription_plan")
            },
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        # Get updated client data for response
        updated_client = clients_collection.find_one({"_id": ObjectId(client_id)})
        
        response_data = {
            "message": "Client subscription updated successfully",
            "updated_data": {
                "subscription_plan": updated_client.get("subscription_plan"),
                "subscription_end": updated_client.get("subscription_end"),
                "questions_allowed": updated_client.get("questions_allowed"),
                "questions_used": updated_client.get("questions_used"),
                "modifications_allowed": updated_client.get("modifications_allowed"),
                "modifications_used": updated_client.get("modifications_used"),
                "is_active": updated_client.get("is_active")
            }
        }
        
        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating client subscription: {str(e)}")

# Add endpoint to refresh CORS origins (for admin use)
@app.post("/admin/refresh-cors")
async def refresh_cors_origins(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # This would require restarting the app to take effect
        # For now, we'll just return the current dynamic origins
        current_origins = get_cors_origins()
        return {
            "message": "CORS origins refreshed (requires app restart for full effect)",
            "current_origins": current_origins
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing CORS: {str(e)}")

# Add admin endpoint to get client details
@app.get("/admin/clients/{client_id}")
async def get_client_details(client_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    clients_collection = db.get_collection("clients")
    employees_collection = db.get_collection("employees")
    questions_collection = db.get_collection("questions")
    subscriptions_collection = db.get_collection("subscriptions")
    
    try:
        client = clients_collection.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get employees for this client
        employees = list(employees_collection.find({"client_id": client_id}))
        
        # Get questions for this client (with pagination)
        page = 1
        per_page = 10
        skip = (page - 1) * per_page
        
        total_questions = questions_collection.count_documents({"client_id": client_id})
        questions = list(questions_collection.find({"client_id": client_id})
                            .skip(skip)
                            .limit(per_page)
                            .sort("created_at", -1))
        
        # Get subscription history
        subscriptions = list(subscriptions_collection.find({"client_id": client_id})
                            .sort("created_at", -1))
        
        # Prepare response
        client_details = {
            "client_info": {
                "_id": str(client["_id"]),
                "name": client.get("name", ""),
                "email": client.get("email", ""),
                "mobile": client.get("mobile", ""),
                "website": client.get("website", ""),
                "business_type": client.get("business_type", ""),
                "location": client.get("location", ""),
                "pan": client.get("pan", ""),
                "tan": client.get("tan", ""),
                "subscription_plan": client.get("subscription_plan", "trial"),
                "subscription_start": client.get("subscription_start"),
                "subscription_end": client.get("subscription_end"),
                "questions_allowed": client.get("questions_allowed", 0),
                "questions_used": client.get("questions_used", 0),
                "modifications_allowed": client.get("modifications_allowed", 0),
                "modifications_used": client.get("modifications_used", 0),
                "allow_edits": client.get("allow_edits", False),
                "allow_deletes": client.get("allow_deletes", False),
                "is_active": client.get("is_active", True),
                "created_at": client.get("created_at")
            },
            "employees": [
                {
                    "_id": str(emp["_id"]),
                    "name": emp.get("name", ""),
                    "email": emp.get("email", ""),
                    "mobile": emp.get("mobile", ""),
                    "website": emp.get("website", ""),
                    "is_active": emp.get("is_active", True),
                    "created_at": emp.get("created_at")
                } for emp in employees
            ],
            "questions": {
                "total": total_questions,
                "page": page,
                "per_page": per_page,
                "data": [
                    {
                        "_id": str(q["_id"]),
                        "question": q.get("question", ""),
                        "answer": q.get("answer", ""),
                        "created_at": q.get("created_at"),
                        "updated_at": q.get("updated_at")
                    } for q in questions
                ]
            },
            "subscriptions": [
                {
                    "_id": str(sub["_id"]),
                    "plan": sub.get("plan", ""),
                    "amount": sub.get("amount", 0),
                    "start_date": sub.get("start_date"),
                    "end_date": sub.get("end_date"),
                    "razorpay_payment_id": sub.get("razorpay_payment_id", ""),
                    "created_at": sub.get("created_at")
                } for sub in subscriptions
            ]
        }
        
        return client_details
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching client details: {str(e)}")

# NEW: Endpoint to sync all client subscriptions
@app.post("/admin/sync-all-subscriptions")
async def sync_all_subscriptions(current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        synced_count = sync_all_clients_subscriptions()
        return {
            "message": f"Successfully synced {synced_count} client subscriptions",
            "synced_count": synced_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing all subscriptions: {str(e)}")


# Question Request endpoints
@app.post("/question-requests")
async def create_question_request(request_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] not in ["client", "employee"]:
        raise HTTPException(status_code=403, detail="Only clients and employees can create question requests")
    
    question_requests_collection = db.get_collection("question_requests")
    notifications_collection = db.get_collection("notifications")
    
    try:
        # Create question request
        question_request = {
            "client_id": str(current_user["_id"]) if current_user["user_type"] == "client" else current_user["client_id"],
            "request_type": request_data["request_type"],
            "question_number": request_data.get("question_number"),
            "question": request_data.get("question"),
            "answer": request_data.get("answer"),
            "status": "pending",
            "created_by": str(current_user["_id"]),
            "created_by_type": current_user["user_type"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = question_requests_collection.insert_one(question_request)
        request_id = str(result.inserted_id)
        
        # Create notification for all admins
        admins_collection = db.get_collection("admins")
        admins = admins_collection.find({})
        
        client_name = current_user.get("name", "Unknown Client")
        request_type_display = request_data["request_type"].replace("_", " ").title()
        
        for admin in admins:
            notification = {
                "user_id": str(admin["_id"]),
                "user_type": "admin",
                "title": f"New Question Request - {request_type_display}",
                "message": f"Client {client_name} has requested a question {request_data['request_type']}",
                "type": "question_request",
                "data": {
                    "request_id": request_id,
                    "client_id": question_request["client_id"],
                    "client_name": client_name,
                    "request_type": request_data["request_type"],
                    "question_number": request_data.get("question_number"),
                    "question": request_data.get("question"),
                    "answer": request_data.get("answer"),
                    "created_by_type": current_user["user_type"]
                },
                "is_read": False,
                "created_at": datetime.utcnow()
            }
            notifications_collection.insert_one(notification)
        
        # Create log
        log_entry = {
            "action": "create_question_request",
            "user_id": str(current_user["_id"]),
            "user_type": current_user["user_type"],
            "client_id": question_request["client_id"],
            "details": {
                "request_id": request_id,
                "request_type": request_data["request_type"]
            },
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Question request submitted successfully", "request_id": request_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating question request: {str(e)}")

@app.get("/question-requests")
async def get_question_requests(current_user: dict = Depends(get_current_user)):
    question_requests_collection = db.get_collection("question_requests")
    
    try:
        if current_user["user_type"] == "admin":
            requests = list(question_requests_collection.find().sort("created_at", -1))
        else:
            client_id = str(current_user["_id"]) if current_user["user_type"] == "client" else current_user["client_id"]
            requests = list(question_requests_collection.find({"client_id": client_id}).sort("created_at", -1))
        
        for req in requests:
            req["_id"] = str(req["_id"])
            req["client_id"] = str(req["client_id"])
        
        return requests
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching question requests: {str(e)}")

@app.put("/question-requests/{request_id}")
async def update_question_request(request_id: str, update_data: dict, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update question requests")
    
    question_requests_collection = db.get_collection("question_requests")
    notifications_collection = db.get_collection("notifications")
    
    try:
        request = question_requests_collection.find_one({"_id": ObjectId(request_id)})
        if not request:
            raise HTTPException(status_code=404, detail="Question request not found")
        
        update_fields = {
            "updated_at": datetime.utcnow()
        }
        
        if "status" in update_data:
            update_fields["status"] = update_data["status"]
        
        if "admin_notes" in update_data:
            update_fields["admin_notes"] = update_data["admin_notes"]
        
        # Update the request
        question_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": update_fields}
        )
        
        # If status changed, create notification for client
        if "status" in update_data:
            notification = {
                "user_id": request["client_id"],
                "user_type": "client",
                "title": f"Question Request {update_data['status'].title()}",
                "message": f"Your question request has been {update_data['status']} by admin",
                "type": "question_request_update",
                "data": {
                    "request_id": request_id,
                    "status": update_data["status"],
                    "admin_notes": update_data.get("admin_notes")
                },
                "is_read": False,
                "created_at": datetime.utcnow()
            }
            notifications_collection.insert_one(notification)
        
        # Create log
        log_entry = {
            "action": "update_question_request",
            "user_id": str(current_user["_id"]),
            "user_type": "admin",
            "client_id": request["client_id"],
            "details": {
                "request_id": request_id,
                "status": update_data.get("status"),
                "previous_status": request.get("status")
            },
            "timestamp": datetime.utcnow()
        }
        db.get_collection("logs").insert_one(log_entry)
        
        return {"message": "Question request updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating question request: {str(e)}")

# Notification endpoints
@app.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    notifications_collection = db.get_collection("notifications")
    
    try:
        notifications = list(notifications_collection.find({
            "user_id": str(current_user["_id"])
        }).sort("created_at", -1).limit(50))
        
        for notification in notifications:
            notification["_id"] = str(notification["_id"])
        
        return notifications
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    notifications_collection = db.get_collection("notifications")
    
    try:
        print(f"🔍 Marking notification as read - ID: {notification_id}, User: {current_user['_id']}")
        
        # Verify the notification exists and belongs to the current user
        notification = notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": str(current_user["_id"])
        })
        
        if not notification:
            print(f"❌ Notification not found or doesn't belong to user")
            raise HTTPException(status_code=404, detail="Notification not found")
        
        print(f"✅ Found notification. Current is_read status: {notification.get('is_read', False)}")
        
        # If already read, just return success
        if notification.get('is_read', False):
            print(f"ℹ️ Notification already read - returning success")
            return {"message": "Notification was already read"}
        
        # Update the notification if not already read
        result = notifications_collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"is_read": True}}
        )
        
        print(f"📝 Update result - Modified count: {result.modified_count}")
        
        if result.modified_count == 0:
            print(f"ℹ️ No documents modified - notification may already be read")
            return {"message": "Notification was already read"}
        
        print(f"✅ Successfully marked notification as read")
        return {"message": "Notification marked as read"}
        
    except Exception as e:
        print(f"❌ Error in mark_notification_read: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error marking notification as read: {str(e)}")
        
@app.get("/notifications/unread-count")
async def get_unread_notifications_count(current_user: dict = Depends(get_current_user)):
    notifications_collection = db.get_collection("notifications")
    
    try:
        count = notifications_collection.count_documents({
            "user_id": str(current_user["_id"]),
            "is_read": False
        })
        
        return {"unread_count": count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error counting unread notifications: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
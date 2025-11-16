import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.sender_email = os.getenv("SMTP_EMAIL")
        self.sender_password = os.getenv("SMTP_PASSWORD")
    
    def send_email(self, to_email, subject, body, is_html=False):
        try:
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = to_email
            message["Subject"] = subject
            
            if is_html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False

email_service = EmailService()

# Email templates
def get_welcome_email_template(name, website):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to SpeechBot!</h1>
            </div>
            <div class="content">
                <h2>Hello {name},</h2>
                <p>Thank you for signing up with SpeechBot! We're excited to have you on board.</p>
                
                <h3>Your Account Details:</h3>
                <ul>
                    <li><strong>Website:</strong> {website}</li>
                    <li><strong>Plan:</strong> Free Trial (5 questions)</li>
                    <li><strong>Trial Period:</strong> 2 days</li>
                </ul>
                
                <h3>Next Steps:</h3>
                <ol>
                    <li>Add your questions and answers</li>
                    <li>Copy the embed script to your website</li>
                    <li>Test the SpeechBot on your site</li>
                </ol>
                
                <p>If you have any questions, feel free to reach out to our support team.</p>
                
                <a href="http://localhost:8000/login" class="button">Get Started</a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    The SpeechBot Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """

def get_password_reset_email_template(name, otp):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .otp {{ font-size: 32px; font-weight: bold; text-align: center; color: #dc3545; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Password Reset Request</h1>
            </div>
            <div class="content">
                <h2>Hello {name},</h2>
                <p>You requested to reset your password. Use the OTP below to verify your identity:</p>
                
                <div class="otp">{otp}</div>
                
                <p>This OTP is valid for 10 minutes. If you didn't request this reset, please ignore this email.</p>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    The SpeechBot Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """

def get_employee_credentials_email_template(employee_name, employee_email, password, website, admin_name):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .credentials {{ background: white; padding: 20px; border-radius: 5px; border-left: 4px solid #28a745; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to SpeechBot Team!</h1>
            </div>
            <div class="content">
                <h2>Hello {employee_name},</h2>
                <p>You have been added to the SpeechBot account for website: <strong>{website}</strong></p>
                
                <div class="credentials">
                    <h3>Your Login Credentials:</h3>
                    <p><strong>Email:</strong> {employee_email}</p>
                    <p><strong>Password:</strong> {password}</p>
                </div>
                
                <p><strong>Important:</strong> Please change your password after first login.</p>
                
                <a href="http://localhost:8000/login" class="button" style="background: #28a745; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Login Now</a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Added by: {admin_name}<br>
                    The SpeechBot Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
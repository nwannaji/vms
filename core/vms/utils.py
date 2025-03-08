
import os
import json
import secrets
from urllib.error import HTTPError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
import qrcode
from pyshorteners import *
import string
import logging
import requests
import pyrebase
from core import settings
from core.settings import USERNAME, API_KEY
from setuptools.command.build import build


# from vms.myViews import test_api_request
from .models import Employee, Visitor
from django.conf import settings

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import base64

# from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client.service_account import ServiceAccountCredentials


# sg = sendgrid.SendGridAPIClient(api_key=os.environ.get(settings.vms_api))
# Initialize Firebase
firebase = pyrebase.initialize_app(settings.FIREBASE_CONFIG)
storage = firebase.storage()
logger = logging.getLogger(__name__)

def get_chart():
     
        # Retrieve all visitors
        visitors = Visitor.objects.all()       
        # Calculate visitor count per department
        department_counts = {}
        total_visitors = 0
        for visitor in visitors:
            dept_name = visitor.get_dept_name()
            if dept_name in department_counts:
                department_counts[dept_name] += 1
            else:
                department_counts[dept_name] = 1
            total_visitors += 1
        
        # Calculate percentage of visitors to each department
        department_percentages = {}
        for dept_name, count in department_counts.items():
            percentage = (count / total_visitors) * 100
            department_percentages[dept_name] = round(percentage, 2)

        # Serialize department_percentages to JSON
        department_percentages_json = json.dumps(department_percentages)
        return department_percentages_json

def generate_qr_code(visitor, name):
    try:
        # Generate QR code content
        qr_code_content = (
            f"Name: {visitor.visitor_name}\n"
            f"Mobile: {visitor.phone_number}\n"
            f"Email: {visitor.email_address}\n"
            f"Host Employee: {Employee.objects.get(employee_name=name)}\n"
            f"Department: {visitor.dept}\n"
            f"Organization: {visitor.organization}"
        )
        
        # Create QR code object
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_code_content)
        qr.make(fit=True)

        # Create directory if it doesn't exist
        qr_code_directory = "static/qr_codes/"
        os.makedirs(qr_code_directory, exist_ok=True)

        # Save QR code as PNG
        qr_code_file_name = f"{visitor.visitor_name}_qr_code.png"
        qr_code_path = os.path.join(qr_code_directory, qr_code_file_name)
        qr.make_image(fill_color="black", back_color="white").save(qr_code_path)

        return qr_code_path
    except Exception as e:
        logger.error(f"Error generating QR code for {visitor.visitor_name}: {e}")
        return None


def generate_otp(visitor):
    # Generate a random OTP
    otp = ''.join(secrets.choices(string.ascii_letters + string.digits) for _ in range(6))
    return otp

# Assuming credentials are stored securely (e.g., Django settings)
def get_credentials():
  """Fetches authorized credentials for Gmail API."""
  scopes = ['https://www.googleapis.com/auth/gmail.send']
  credentials_file = "vms\\credentials.json"
  credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scopes)
  return credentials

def build_email_message(sender_email, visitor, subject, body):
    try:
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = visitor.email_address
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        # Generate QR code
        qr_code_path = generate_qr_code(visitor, visitor.visitor_name)

        # Attach QR code if generated
        if qr_code_path and os.path.exists(qr_code_path):
            with open(qr_code_path, 'rb') as qr_file:
                img_data = qr_file.read()
                image_part = MIMEImage(img_data)
                image_part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(qr_code_path))
                message.attach(image_part)
        
        return message.as_string().encode('utf-8')
    except Exception as e:
        logger.error(f"Error building email for {visitor.visitor_name}: {e}")
        return None

    
    
def upload_qr_code_to_firebase(img_name, img_data):
    try:
        # Define the path for the image in Firebase Storage
        image_path = f'qr_Code_Images/{img_name}'

        # Upload the image data to Firebase Storage
        path = storage.child(image_path).put(img_data)

        # Get the public URL of the uploaded image
        public_url = storage.child(image_path).get_url(None)
        global URL 
        URL =public_url
        return URL
    except Exception as e:
        logger.error(f"Error uploading QR code {img_name} to Firebase: {e}")
        return None

def send_visitor_whatsApp_message_without_qrCode(visitor):
    username = USERNAME
    api_key = API_KEY
    try:
        # Generate message content
        # qr_code_path = URL
        message = (
            f"Dear {visitor.visitor_name},\n"
            f"Your request to visit {visitor.get_employee_name()} in {visitor.dept} at NigComSat LTD.\n"
            f"has been submitted, and is currently awaiting for approval.\n"
            f"NigComSat VMS Team"
        )

        data = {
            "WA": {
                "auth": {
                    "username": username,
                    "apikey": api_key,
                },
                "message": {
                    "subject": "Visitor QR Code",
                    "messagetext": message,
                },
                "recipients": [visitor.phone_number],
            }
        }

        # Send request
        response = requests.post(
            "https://api.ebulksms.com/sendwhatsapp.json", 
            headers={"Content-Type": "application/json"}, 
            json=data
        )
        if response.status_code == 200:
            logger.info(f"WhatsApp message sent successfully to {visitor.phone_number}.")
        else:
            logger.error(f"Failed to send WhatsApp message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {visitor.phone_number}: {e}")


def send_employee_whatsApp_message(employee, visitor):
    # Replace with your eBulkSMS credentials
    username = USERNAME
    api_key = API_KEY

    url = 'https://host_url/checkIn/'

    # Recipient phone number (including country code)
    # Subject (not shown to recipient)
    subject = "Visitor Request Notification"

    # Your message content
    msg = f"""
    Dear, {employee.employee_name}
    This is to inform you that {visitor.visitor_name} with mobile number { visitor.phone_number } from {visitor.organization} has requested to visit you in the {employee.dept_name} department.
    Please, if this visit is convenient for you, log into the VMS portal: {url} to approve it by inserting and submitting the visitor's ID in the textbox provided. 
    Else, click on the Decline button below to reject the visit.
    Thanks,
    NigComSat Visitors Mgt Team.
    """
    # Construct the JSON data
    data = {
        "WA": {
            "auth": {
                "username": username,
                "apikey": api_key, 
            },
            "message": {
                "subject": subject,
                "messagetext": msg,
            },
            "recipients": [employee.phone_number],
        }
    }

    # Set the headers
    headers = {"Content-Type": "application/json"}

    # Send the POST request
    url = "https://api.ebulksms.com/sendwhatsapp.json"
    response = requests.post(url, headers=headers, json=data)

    # Check for successful response
    if response.status_code == 200:
        print("Message sent successfully!")
    else:
        print(f"Error sending message: {response.text}")

def send_visitor_whatsApp_message_with_qrCode(visitor):
    username = USERNAME
    api_key = API_KEY
    try:
        # Generate message content
        qr_code_path = URL
        url = Shortener().tinyurl.short(qr_code_path)  # Convert the QR code URL to a shortened version
        message = (
            f"Dear {visitor.visitor_name},\n"
            f"Your request to visit {visitor.get_employee_name()} in {visitor.dept} at NigComSat LTD.\n"
            f"has been approved. The link for your QR-Code base Identity & Access Management (IAM) is below.\n"
            f"{url},please endeavour to present it at the Entrance Gate.\n"
            f"NigComSat VMS Team"
        )

        data = {
            "WA": {
                "auth": {
                    "username": username,
                    "apikey": api_key,
                },
                "message": {
                    "subject": "Visitor QR Code",
                    "messagetext": message,
                },
                "recipients": [visitor.phone_number]
            }
        }

        # Send request
        response = requests.post(
            "https://api.ebulksms.com/sendwhatsapp.json", 
            headers={"Content-Type": "application/json"}, 
            json=data
        )
        if response.status_code == 200:
            logger.info(f"WhatsApp message sent successfully to {visitor.phone_number}.")
        else:
            logger.error(f"Failed to send WhatsApp message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {visitor.phone_number}: {e}")

def send_visitor_whatsapp_message_reschedule(visitor, reschedule_time):
    username = USERNAME
    api_key = API_KEY
    try:
        # Generate message content with new scheduled time details
        qr_code_path = URL  # This should be set to the QR code URL path relevant to your app
        # Shorten the QR code URL for a cleaner message
        shortened_url = Shortener().tinyurl.short(qr_code_path)
        message = (
            f"Dear {visitor.visitor_name},\n"
            f"Your scheduled visit to {visitor.get_employee_name()} in {visitor.dept} at NigComSat LTD has been re-scheduled.\n"
            f"Your new visit date & time is: {reschedule_time}.\n"
            f"Please use the QR-Code link below for your Identity & Access Management (IAM) at the Entrance Gate:\n"
            f"{shortened_url}\n"
            f"Thank you,\nNigComSat VMS Team"
        )

        data = {
            "WA": {
                "auth": {
                    "username": username,
                    "apikey": api_key,
                },
                "message": {
                    "subject": "Visitor Reschedule Notification",
                    "messagetext": message,
                },
                "recipients": [visitor.phone_number]
            }
        }

        # Send the WhatsApp message request
        response = requests.post(
            "https://api.ebulksms.com/sendwhatsapp.json",
            headers={"Content-Type": "application/json"},
            json=data
        )
        if response.status_code == 200:
            logger.info(f"WhatsApp message sent successfully to {visitor.phone_number}.")
        else:
            logger.error(f"Failed to send WhatsApp message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {visitor.phone_number}: {e}")

    





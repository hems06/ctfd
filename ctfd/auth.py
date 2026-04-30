import os
from flask import render_template, request, redirect, url_for, flash, Blueprint
from CTFd.models import db, Users
from CTFd.utils import get_config
from CTFd.utils.decorators import authed_only
from CTFd.auth import auth as auth_bp
from CTFd.utils.crypto import verify_password
from CTFd.utils.logging import log

# Path to the verified emails file
WHITELIST_FILE = '/opt/CTFd/emails.txt'

def is_email_whitelisted(email):
    if not os.path.exists(WHITELIST_FILE):
        print(f"[!] Whitelist file {WHITELIST_FILE} not found. Allowing all.")
        return True
    
    try:
        with open(WHITELIST_FILE, 'r') as f:
            whitelisted_emails = {line.strip().lower() for line in f if line.strip()}
        return email.lower() in whitelisted_emails
    except Exception as e:
        print(f"[ERROR] Failed to read whitelist: {e}")
        return False

# We will monkeypatch the registration logic or inject a check.
# However, a cleaner way for a standalone auth.py override is to define the register route.

original_register = auth_bp.view_functions.get('register')

def whitelisted_register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not is_email_whitelisted(email):
            flash('This email is not authorized for this event. Please use your registered email.', 'danger')
            return render_template('register.html', errors=['Unauthorized Email'])
            
    # If it's a GET or a whitelisted POST, proceed with original logic
    return original_register()

# Override the registration route
auth_bp.view_functions['register'] = whitelisted_register

# Re-export the blueprint if needed, but since we are modifying the module-level auth_bp
# which CTFd imports, this should work if this file is imported/placed correctly.

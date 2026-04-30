from flask import request, render_template, flash
import os

def load(app):
    # Get the original register route
    from CTFd.auth import auth
    original_register = auth.view_functions.get('register')

    # Path inside the container as defined in docker-compose
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

    def whitelisted_register():
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            if not is_email_whitelisted(email):
                flash('This email is not authorized for this event. Please use your registered email.', 'danger')
                return render_template('register.html', errors=['Unauthorized Email'])
                
        # If it's a GET or a whitelisted POST, proceed with original logic
        return original_register()

    # Override the registration route
    auth.view_functions['register'] = whitelisted_register
    print("[*] Whitelist Auth Plugin Loaded")

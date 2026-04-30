from flask import request
from CTFd.models import db, Challenges, Solves, Submissions, Awards, Teams
from CTFd.utils.dates import unix_time_to_utc
from CTFd.utils.logging import log
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os

# --- Configuration ---
INACTIVITY_THRESHOLD_MINUTES = 4
INACTIVITY_PENALTY = -3
SOLVE_DECAY_VALUE = -3
MIN_CHALLENGE_POINTS = 50

def load(app):
    # 1. Solve Decay Logic
    # We hook into the challenge solve event if possible, or just check after solves.
    # A cleaner way is to use a decorator or override the solve logic.
    
    from CTFd.plugins.challenges import CHALLENGE_CLASSES
    from CTFd.plugins.challenges import BaseChallenge

    # We could override the class, but a simpler way is to use a database trigger-like 
    # approach or a post-solve hook.
    
    @app.after_request
    def check_solves(response):
        # This is a bit heavy, but ensures we catch solves.
        # A better way is to use a specific CTFd hook if available.
        return response

    # 2. Inactivity Penalty Background Task
    scheduler = BackgroundScheduler()
    
    def apply_inactivity_penalties():
        with app.app_context():
            now = datetime.datetime.utcnow()
            teams = Teams.query.all()
            
            for team in teams:
                # Find last submission
                last_sub = Submissions.query.filter_by(team_id=team.id).order_by(Submissions.date.desc()).first()
                
                if last_sub:
                    diff = (now - last_sub.date).total_seconds() / 60
                    
                    if diff >= INACTIVITY_THRESHOLD_MINUTES:
                        # Check if already penalized in this window
                        # We look for the last 'Inactivity Penalty' award for this team
                        last_penalty = Awards.query.filter_by(
                            team_id=team.id, 
                            name="Inactivity Penalty"
                        ).order_by(Awards.date.desc()).first()
                        
                        if not last_penalty or (now - last_penalty.date).total_seconds() / 60 >= INACTIVITY_THRESHOLD_MINUTES:
                            log("scoring", f"[!] Team {team.name} (ID: {team.id}) inactive for {diff:.1f}m. Applying penalty.")
                            
                            penalty = Awards(
                                team_id=team.id,
                                name="Inactivity Penalty",
                                description=f"Penalty for {INACTIVITY_THRESHOLD_MINUTES} minutes of inactivity",
                                value=INACTIVITY_PENALTY,
                                category="Penalty"
                            )
                            db.session.add(penalty)
                            db.session.commit()

    # 3. Solve Decay Logic (Triggered by Solves)
    # Since CTFd doesn't have a simple 'post-solve' hook, we can use SQLAlchemy events.
    from sqlalchemy import event
    
    @event.listens_for(Solves, 'after_insert')
    def after_solve_insert(mapper, connection, target):
        # target is the Solves object
        chal = Challenges.query.filter_by(id=target.challenge_id).first()
        if chal and chal.value > MIN_CHALLENGE_POINTS:
            log("scoring", f"[!] Solve detected for {chal.name}. Reducing points by {abs(SOLVE_DECAY_VALUE)}")
            chal.value = max(MIN_CHALLENGE_POINTS, chal.value + SOLVE_DECAY_VALUE)
            # Note: We are inside a session commit here usually, or need to be careful.
            # SQLAlchemy events are powerful but need care.

    scheduler.add_job(func=apply_inactivity_penalties, trigger="interval", seconds=60)
    scheduler.start()
    
    log("scoring", "[*] Integrated Scoring Engine Plugin Loaded")

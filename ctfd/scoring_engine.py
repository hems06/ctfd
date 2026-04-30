import time
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Configuration ---
DB_URL = "mysql+pymysql://ctfd:ctfd@db/ctfd"  # Update with your DB credentials
INACTIVITY_THRESHOLD_MINUTES = 4
INACTIVITY_PENALTY = -3
SOLVE_DECAY_VALUE = -3
MIN_CHALLENGE_POINTS = 50  # Challenges won't go below this

Base = declarative_base()

class Teams(Base):
    __tablename__ = 'teams'
    id = Column(Integer, primary_key=True)
    name = Column(Integer)

class Challenges(Base):
    __tablename__ = 'challenges'
    id = Column(Integer, primary_key=True)
    value = Column(Integer)
    name = Column(String)

class Solves(Base):
    __tablename__ = 'solves'
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey('challenges.id'))
    team_id = Column(Integer, ForeignKey('teams.id'))
    date = Column(DateTime, default=datetime.datetime.utcnow)

class Submissions(Base):
    __tablename__ = 'submissions'
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'))
    date = Column(DateTime, default=datetime.datetime.utcnow)

class Awards(Base):
    __tablename__ = 'awards'
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'))
    name = Column(String)
    description = Column(String)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    value = Column(Integer)
    category = Column(String)

def main():
    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("[*] CTFd Dynamic Scoring Engine Started")
    
    last_processed_solve_id = 0
    # Store last penalty time for each team to avoid constant penalizing
    last_penalty_time = {} 

    while True:
        try:
            # 1. Process Solve Point Decay
            new_solves = session.query(Solves).filter(Solves.id > last_processed_solve_id).all()
            for solve in new_solves:
                chal = session.query(Challenges).filter(Challenges.id == solve.challenge_id).first()
                if chal and chal.value > MIN_CHALLENGE_POINTS:
                    print(f"[!] Solve detected for {chal.name}. Reducing points by {abs(SOLVE_DECAY_VALUE)}")
                    chal.value = max(MIN_CHALLENGE_POINTS, chal.value + SOLVE_DECAY_VALUE)
                last_processed_solve_id = max(last_processed_solve_id, solve.id)
            
            # 2. Process Inactivity Penalties
            teams = session.query(Teams).all()
            now = datetime.datetime.utcnow()
            
            for team in teams:
                # Find last submission (any flag attempt, correct or not)
                last_sub = session.query(Submissions).filter(Submissions.team_id == team.id).order_by(desc(Submissions.date)).first()
                
                if last_sub:
                    diff = (now - last_sub.date).total_seconds() / 60
                    
                    if diff >= INACTIVITY_THRESHOLD_MINUTES:
                        # Check if we already penalized them for this specific window
                        last_p = last_penalty_time.get(team.id)
                        if not last_p or (now - last_p).total_seconds() / 60 >= INACTIVITY_THRESHOLD_MINUTES:
                            print(f"[!] Team {team.id} inactive for {diff:.1f}m. Applying {INACTIVITY_PENALTY} penalty.")
                            
                            penalty = Awards(
                                team_id=team.id,
                                name="Inactivity Penalty",
                                description=f"Penalty for {INACTIVITY_THRESHOLD_MINUTES} minutes of inactivity",
                                value=INACTIVITY_PENALTY,
                                category="Penalty"
                            )
                            session.add(penalty)
                            last_penalty_time[team.id] = now

            session.commit()
            
        except Exception as e:
            print(f"[ERROR] {e}")
            session.rollback()
        
        time.sleep(30) # Check every 30 seconds

if __name__ == "__main__":
    main()

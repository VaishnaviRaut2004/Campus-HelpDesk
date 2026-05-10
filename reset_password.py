import sys
from app import app, db, User
from werkzeug.security import generate_password_hash

def reset_password(name, new_password):
    with app.app_context():
        user = User.query.filter_by(name=name).first()
        if not user:
            print(f"Error: User with name '{name}' not found.")
            return
        
        user.password = generate_password_hash(new_password)
        db.session.commit()
        print(f"Success! Changed the password for user '{name}'.")
        print(f"They can now log in with email: {user.email}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py \"User Name\" \"new_password\"")
        print("Example: python reset_password.py \"IT User\" \"securepass123\"")
    else:
        reset_password(sys.argv[1], sys.argv[2])

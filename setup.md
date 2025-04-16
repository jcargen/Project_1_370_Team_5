# Bocces Stats Tracker
This is a game/player stat tracker for the Bocce.
### Frontend
- HTML, CSS, JavaScript + GraphQL Queries
- Users can view player & game information as well as add players & games
### Backend
- Python, Flask, Ariadne, GraphQL
- Resolvers for adding & removing players and games, as well as getting other information
### Database
- MongoDB

# Setup

## Dependencies:
pip install flask flask-cors pymongo ariadne

## Start backend
export FLASK_APP=server/backend.py
flask run

## Start frontend
cd client
python -m http.server 8000


## Connection 
@ http://localhost:8000

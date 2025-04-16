from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from ariadne import QueryType, MutationType, make_executable_schema, graphql_sync
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from ariadne import ObjectType
from flask import render_template, request

app = Flask(__name__)
CORS(app)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['bocce_stats']
players_collection = db['players']

# Define types using Schema Definition Language (SDL)
type_defs = """
    type Game {
        date: String!
        opponent: String!
        score: String!
        result: String!
        ballColor: String
        location: String
        weather: String
        duration: Int
        notes: String
    }

    type PlayerStats {
        gamesPlayed: Int!
        gamesWon: Int!
        winPercentage: Float!
        redBallWinRate: Float!
        greenBallWinRate: Float!
        averagePoints: Float!
        highestScore: Int!
        currentStreak: Int!
        longestStreak: Int!
    }

    type Player {
        id: ID!
        name: String!
        games: [Game!]!
        stats: PlayerStats!
    }

    type Query {
        players: [Player!]!
        player(id: ID!): Player
    }

    type AddPlayerResult {
        player: Player
    }

    type DeleteResult {
        success: Boolean!
    }

    type AddGameResult {
        success: Boolean!
        game: Game
    }

    type Mutation {
        addPlayer(name: String!): AddPlayerResult!
        deletePlayer(id: ID!): DeleteResult!
        addGame(
            playerId: ID!, 
            opponent: String!, 
            date: String,
            score: String!, 
            result: String!,
            ballColor: String,
            location: String,
            weather: String,
            duration: Int,
            notes: String
        ): AddGameResult!
        deleteGame(
            playerId: ID!,
            date: String!,
            opponent: String!
        ): DeleteResult!
    }
"""

# Set up resolvers
query = QueryType()
mutation = MutationType()
player_object = ObjectType("Player")

@player_object.field("stats")
def resolve_player_stats(player, _):
    games = player.get('games', [])
    
    # Basic statistics
    games_played = len(games)
    games_won = sum(1 for game in games if game.get('result') == 'win')
    win_percentage = (games_won / games_played * 100) if games_played > 0 else 0
    
    # Ball color statistics
    red_games = [g for g in games if g.get('ballColor') == 'red']
    red_wins = sum(1 for g in red_games if g.get('result') == 'win')
    red_win_rate = (red_wins / len(red_games) * 100) if len(red_games) > 0 else 0
    
    green_games = [g for g in games if g.get('ballColor') == 'green']
    green_wins = sum(1 for g in green_games if g.get('result') == 'win')
    green_win_rate = (green_wins / len(green_games) * 100) if len(green_games) > 0 else 0
    
    # Score statistics
    scores = []
    for game in games:
        try:
            score_parts = game.get('score', '0-0').split('-')
            if len(score_parts) == 2:
                player_score = int(score_parts[0].strip())
                scores.append(player_score)
        except ValueError:
            pass
            
    avg_points = sum(scores) / len(scores) if scores else 0
    highest_score = max(scores) if scores else 0
    
    # Streak calculation
    current_streak = 0
    longest_streak = 0
    current_type = None
    
    sorted_games = sorted(games, key=lambda g: g.get('date', ''), reverse=True)
    
    for game in sorted_games:
        result = game.get('result')
        if current_type is None:
            current_type = result
            current_streak = 1
        elif current_type == result:
            current_streak += 1
        else:
            current_type = result
            current_streak = 1
            
        if current_streak > longest_streak and result == 'win':
            longest_streak = current_streak
            
    return {
        "gamesPlayed": games_played,
        "gamesWon": games_won,
        "winPercentage": round(win_percentage, 1),
        "redBallWinRate": round(red_win_rate, 1),
        "greenBallWinRate": round(green_win_rate, 1),
        "averagePoints": round(avg_points, 1),
        "highestScore": highest_score,
        "currentStreak": current_streak if current_type == 'win' else 0,
        "longestStreak": longest_streak
    }

@query.field("players")
def resolve_players(*_):
    return list(players_collection.find({}, {'_id': False}))

@query.field("player")
def resolve_player(_, info, id):
    return players_collection.find_one({"id": int(id)}, {'_id': False})

@mutation.field("addPlayer")
def resolve_add_player(_, info, name):
    player_data = {
        "id": int(players_collection.count_documents({})) + 1,
        "name": name,
        "games": []
    }
    players_collection.insert_one(player_data)
    return {"player": player_data}

@mutation.field("deletePlayer")
def resolve_delete_player(_, info, id):
    result = players_collection.delete_one({"id": int(id)})
    return {"success": result.deleted_count > 0}

@mutation.field("addGame")
def resolve_add_game(_, info, playerId, opponent, date=None, score=None, result=None, 
                    ballColor=None, location=None, weather=None, duration=None, notes=None):
    if not date:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
        
    game_data = {
        "opponent": opponent,
        "date": date,
        "score": score,
        "result": result,
        "ballColor": ballColor,
        "location": location,
        "weather": weather,
        "duration": duration,
        "notes": notes
    }
    
    # Filter None values
    game_data = {k: v for k, v in game_data.items() if v is not None}
    
    result = players_collection.update_one(
        {"id": int(playerId)},
        {"$push": {"games": game_data}}
    )
    
    return {"success": result.modified_count > 0, "game": game_data}

@mutation.field("deleteGame")
def resolve_delete_game(_, info, playerId, date, opponent):
    result = players_collection.update_one(
        {"id": int(playerId)},
        {"$pull": {"games": {"date": date, "opponent": opponent}}}
    )
    
    return {"success": result.modified_count > 0}

# Create executable schema
schema = make_executable_schema(type_defs, [query, mutation, player_object])

# GraphQL endpoint
@app.route("/graphql", methods=["GET"])
def graphql_playground():
    # Serve GraphiQL for newer versions of Ariadne
    graphiql_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GraphiQL</title>
        <link href="https://unpkg.com/graphiql/graphiql.min.css" rel="stylesheet" />
    </head>
    <body style="margin: 0;">
        <div id="graphiql" style="height: 100vh;"></div>
        <script
            crossorigin
            src="https://unpkg.com/react/umd/react.production.min.js"
        ></script>
        <script
            crossorigin
            src="https://unpkg.com/react-dom/umd/react-dom.production.min.js"
        ></script>
        <script
            crossorigin
            src="https://unpkg.com/graphiql/graphiql.min.js"
        ></script>
        <script>
            const fetcher = GraphiQL.createFetcher({
                url: '/graphql',
            });
            ReactDOM.render(
                React.createElement(GraphiQL, { fetcher }),
                document.getElementById('graphiql'),
            );
        </script>
    </body>
    </html>
    """
    return graphiql_html, 200

@app.route("/graphql", methods=["POST"])
def graphql_server():
    # GraphQL queries are always sent as POST
    data = request.get_json()
    
    # Execute the query
    success, result = graphql_sync(
        schema,
        data,
        context_value={"request": request},
        debug=app.debug
    )
    
    # Return the result
    return jsonify(result), 200 if success else 400

@app.route('/')
def hello():
    return 'Bocce Stats API with GraphQL - Access the GraphQL interface at /graphql'

if __name__ == '__main__':
    app.run(debug=True)
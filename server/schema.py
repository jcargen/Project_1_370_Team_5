import graphene
from graphene.relay import Node
from pymongo import MongoClient
from bson.objectid import ObjectId

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['bocce_stats']
players_collection = db['players']

# Types
class Game(graphene.ObjectType):
    id = graphene.ID()
    date = graphene.String()
    opponent = graphene.String()
    score = graphene.String()
    result = graphene.String()
    ball_color = graphene.String()
    location = graphene.String()
    weather = graphene.String()
    duration = graphene.Int()
    notes = graphene.String()

class PlayerStats(graphene.ObjectType):
    games_played = graphene.Int()
    games_won = graphene.Int()
    win_percentage = graphene.Float()
    red_ball_win_rate = graphene.Float()
    green_ball_win_rate = graphene.Float()
    average_points = graphene.Float()
    highest_score = graphene.Int()
    current_streak = graphene.Int()
    longest_streak = graphene.Int()

class Player(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    games = graphene.List(Game)
    stats = graphene.Field(PlayerStats)
    
    def resolve_stats(self, info):
        games = self.get('games', [])
        
        # Basic statistics
        games_played = len(games)
        games_won = sum(1 for game in games if game.get('result') == 'win')
        win_percentage = (games_won / games_played * 100) if games_played > 0 else 0
        
        # Ball color statistics
        red_games = [g for g in games if g.get('ball_color') == 'red']
        red_wins = sum(1 for g in red_games if g.get('result') == 'win')
        red_win_rate = (red_wins / len(red_games) * 100) if len(red_games) > 0 else 0
        
        green_games = [g for g in games if g.get('ball_color') == 'green']
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
                
        return PlayerStats(
            games_played=games_played,
            games_won=games_won,
            win_percentage=round(win_percentage, 1),
            red_ball_win_rate=round(red_win_rate, 1),
            green_ball_win_rate=round(green_win_rate, 1),
            average_points=round(avg_points, 1),
            highest_score=highest_score,
            current_streak=current_streak if current_type == 'win' else 0,
            longest_streak=longest_streak
        )

# Queries
class Query(graphene.ObjectType):
    players = graphene.List(Player)
    player = graphene.Field(Player, id=graphene.ID(required=True))
    
    def resolve_players(self, info):
        return list(players_collection.find({}, {'_id': False}))
    
    def resolve_player(self, info, id):
        return players_collection.find_one({"id": int(id)}, {'_id': False})

# Mutations
class AddPlayer(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
    
    player = graphene.Field(Player)
    
    def mutate(self, info, name):
        player_data = {
            "id": int(players_collection.count_documents({})) + 1,
            "name": name,
            "games": []
        }
        players_collection.insert_one(player_data)
        return AddPlayer(player=player_data)

class DeletePlayer(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, id):
        result = players_collection.delete_one({"id": int(id)})
        return DeletePlayer(success=result.deleted_count > 0)

class AddGame(graphene.Mutation):
    class Arguments:
        player_id = graphene.ID(required=True)
        opponent = graphene.String(required=True)
        date = graphene.String()
        score = graphene.String(required=True)
        result = graphene.String(required=True)
        ball_color = graphene.String()
        location = graphene.String()
        weather = graphene.String()
        duration = graphene.Int()
        notes = graphene.String()
    
    success = graphene.Boolean()
    game = graphene.Field(Game)
    
    def mutate(self, info, player_id, opponent, date=None, score=None, result=None, 
               ball_color=None, location=None, weather=None, duration=None, notes=None):
        if not date:
            from datetime import datetime
            date = datetime.now().strftime('%Y-%m-%d')
            
        game_data = {
            "opponent": opponent,
            "date": date,
            "score": score,
            "result": result,
            "ball_color": ball_color,
            "location": location,
            "weather": weather,
            "duration": duration,
            "notes": notes
        }
        
        # Filter None values
        game_data = {k: v for k, v in game_data.items() if v is not None}
        
        result = players_collection.update_one(
            {"id": int(player_id)},
            {"$push": {"games": game_data}}
        )
        
        return AddGame(success=result.modified_count > 0, game=game_data)

class DeleteGame(graphene.Mutation):
    class Arguments:
        player_id = graphene.ID(required=True)
        date = graphene.String(required=True)
        opponent = graphene.String(required=True)
    
    success = graphene.Boolean()
    
    def mutate(self, info, player_id, date, opponent):
        result = players_collection.update_one(
            {"id": int(player_id)},
            {"$pull": {"games": {"date": date, "opponent": opponent}}}
        )
        
        return DeleteGame(success=result.modified_count > 0)

class Mutation(graphene.ObjectType):
    add_player = AddPlayer.Field()
    delete_player = DeletePlayer.Field()
    add_game = AddGame.Field()
    delete_game = DeleteGame.Field()

schema = graphene.Schema(query=Query, mutation=Mutation)
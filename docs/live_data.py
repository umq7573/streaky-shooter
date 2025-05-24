# %% [markdown]
# # Working with NBA live data...
# Libraries supporting live data do not include support for Pandas. Note: Any call to `{endpoint}.{Class}()` will perform a request. Example: `scoreboard.ScoreBoard()`. In order to avoid multiple requests, set `{endpoint}.{Class}()` to a variable. See sample code below.

# %% [markdown]
# ## Today's Score Board
# 

# %%
# Query nba.live.endpoints.scoreboard and  list games in localTimeZone
from datetime import datetime, timezone
from dateutil import parser
from nba_api.live.nba.endpoints import scoreboard

f = "{gameId}: {awayTeam} vs. {homeTeam} @ {gameTimeLTZ}" 

board = scoreboard.ScoreBoard()
print("ScoreBoardDate: " + board.score_board_date)
games = board.games.get_dict()
for game in games:
    gameTimeLTZ = parser.parse(game["gameTimeUTC"]).replace(tzinfo=timezone.utc).astimezone(tz=None)
    print(f.format(gameId=game['gameId'], awayTeam=game['awayTeam']['teamName'], homeTeam=game['homeTeam']['teamName'], gameTimeLTZ=gameTimeLTZ))

# %% [markdown]
# ## Box Score

# %%
# Get BoxScore
from nba_api.live.nba.endpoints import boxscore
box = boxscore.BoxScore('0022000196') 

# %%
# Data Sets
box.game.get_dict()                    #equal to box.get_dict()['game']
#box.arena.get_dict()                  #equal to box.get_dict()['game']['arena']
#box.away_team.get_dict()              #equal to box.get_dict()['game']['awayTeam']
#box.away_team_player_stats.get_dict() #equal to box.get_dict()['game']['awayTeam']['players']
#box.away_team_stats.get_dict()        #equal to box.get_dict()['game']['homeTeam'] w/o ['players']
#box.home_team.get_dict()              #equal to box.get_dict()['game']['homeTeam']
#box.home_team_player_stats.get_dict() #equal to box.get_dict()['game']['homeTeam']['players']
#box.home_team_stats.get_dict()        #equal to box.get_dict()['game']['homeTeam'] w/o ['players']
#box.game_details.get_dict()           #equal to box.get_dict()['game'] scrubbed of all other dictionaries
#box.officials.get_dict()              #equal to box.get_dict()['game']['officials']

# %%
# Getting Box Scores. 
# Note: home_team & away_team have the identicial data structure.
players = box.away_team.get_dict()['players']
f = "{player_id}: {name}: {points} PTS"
for player in players:
    print(f.format(player_id=player['personId'],name=player['name'],points=player['statistics']['points']))

# %% [markdown]
# ## Play By Play Data

# %%
# Query nba.live.endpoints for the score board of GameID 0022000180 = NYK vs BOS
# Simple PlayByPlay Loop demonstrating data usage
from nba_api.live.nba.endpoints import playbyplay
from nba_api.stats.static import players

pbp = playbyplay.PlayByPlay('0022000196')
line = "{action_number}: {period}:{clock} {player_id} ({action_type})"
actions = pbp.get_dict()['game']['actions'] #plays are referred to in the live data as `actions`
for action in actions:
    player_name = ''
    player = players.find_player_by_id(action['personId'])
    if player is not None:
        player_name = player['full_name']
    print(line.format(action_number=action['actionNumber'],period=action['period'],clock=action['clock'],action_type=action['actionType'],player_id=player_name))

# %% [markdown]
# # Bettings Odds Data

# %%
from nba_api.live.nba.endpoints import Odds
import json

# Fetch odds data
odds = Odds()
games_list = odds.get_games().get_dict()

# Print first 2 games with nice formatting
print(json.dumps(games_list[:3], indent=2))

# %% [markdown]
# You can further analyze by using other functionality available as a part of this library to extract meaning from the raw data. In example:

# %%
from nba_api.live.nba.endpoints import Odds
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder

# Fetch odds data for today's NBA games
odds = Odds()
games_list = odds.get_games().get_dict()

# Get first game only
game = games_list[0]
game_id = game.get('gameId', 'Unknown')
home_team = teams._find_team_name_by_id(game['homeTeamId'])['full_name'] # Use teams module to get team names
away_team = teams._find_team_name_by_id(game['awayTeamId'])['full_name']

# Get game date using LeagueGameFinder
gamefinder = leaguegamefinder.LeagueGameFinder(
    league_id_nullable="00",
    game_id_nullable=game_id
)
game_info = gamefinder.get_data_frames()[0]
specific_game = game_info[game_info['GAME_ID'] == game_id]
game_date = specific_game['GAME_DATE'].iloc[0]

# Display basic game information
print(f"Game ID: {game_id}")
print(f"Game Date: {game_date}")
print(f"Home Team: {home_team}")
print(f"Away Team: {away_team}")

# Display 2-way odds
two_way_market = next((m for m in game['markets'] if m['name'] == '2way'), None)
if two_way_market and two_way_market['books']:
    first_book = two_way_market['books'][0]
    print(f"\n2-way Odds from {first_book['name']}:")
    for outcome in first_book['outcomes']:
        team_type = outcome['type']
        team_name = home_team if team_type == 'home' else away_team
        odds = outcome['odds']
        print(f"  {team_type.capitalize()} ({team_name}): {odds}")
        trend = outcome['odds_trend']
        print(f"  Odds trend is: {trend}")
        opening = outcome['opening_odds']
        print(f"  Opening odds were: {opening}")

# Display spread odds
spread_market = next((m for m in game['markets'] if m['name'] == 'spread'), None)
if spread_market and spread_market['books']:
    first_book = spread_market['books'][0]
    print(f"\nSpread Odds from {first_book['name']}:")
    for outcome in first_book['outcomes']:
        team_type = outcome['type']
        team_name = home_team if team_type == 'home' else away_team
        spread = outcome.get('spread', 'N/A')
        odds = outcome['odds']
        print(f"  {team_type.capitalize()} ({team_name}) with spread {spread}: {odds}")
        trend = outcome['odds_trend']
        print(f"  Odds trend is: {trend}")
        opening = outcome['opening_odds']
        print(f"  Opening odds: {opening}")
        opening_spread = outcome['opening_spread']
        print(f"  Opening spread: {opening_spread}")



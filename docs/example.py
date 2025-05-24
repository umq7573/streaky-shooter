# %% [markdown]
# # Basics and Package Structure
# 
# If you're just interested in pulling data, you will primarily be using `nba_api.stats.endpoints`.
# This submodule contains a class for each API endpoint supported by stats.nba.com.
# For example, [the PlayerCareerStats class](https://github.com/swar/nba_api/blob/master/nba_api/stats/endpoints/playercareerstats.py) is initialized with a player ID and returns some career statistics for the player.

# %%
from nba_api.stats.endpoints import playercareerstats

# Anthony Davis
career = playercareerstats.PlayerCareerStats(player_id="203076")
career.get_data_frames()[0]

# %% [markdown]
# `career`, above, is a `PlayerCareerStats` object.
# This class (and the other endpoint classes) supports several methods of accessing the data: `get_dict()`, `get_json()`, `get_data_frames()`, and more.
# `get_data_frames()` returns a list of pandas DataFrames, and when working in notebooks, this is often your best option for viewing data.
# In general, the first DataFrame in this list is the primary returned data structure and the one you'll want to look at.
# 
# Almost all of the endpoint classes take at least one required argument, along with several optional ones.
# In the case of `PlayerCareerStats`, a player ID is required, but the user may also specify a league ID.

# %% [markdown]
# At the time of writing this notebook, these are the endpoints available:
# 
# <table><tr></tr><tr><td>boxscoreadvancedv2</td><td>boxscorefourfactorsv2</td><td>boxscoremiscv2</td><td>boxscoreplayertrackv2</td></tr><tr><td>boxscorescoringv2</td><td>boxscoresummaryv2</td><td>boxscoretraditionalv2</td><td>boxscoreusagev2</td></tr><tr><td>commonallplayers</td><td>commonplayerinfo</td><td>commonplayoffseries</td><td>commonteamroster</td></tr><tr><td>commonteamyears</td><td>defensehub</td><td>draftcombinedrillresults</td><td>draftcombinenonstationaryshooting</td></tr><tr><td>draftcombineplayeranthro</td><td>draftcombinespotshooting</td><td>draftcombinestats</td><td>drafthistory</td></tr><tr><td>franchisehistory</td><td>homepageleaders</td><td>homepagev2</td><td>infographicfanduelplayer</td></tr><tr><td>leaderstiles</td><td>leaguedashlineups</td><td>leaguedashplayerbiostats</td><td>leaguedashplayerclutch</td></tr><tr><td>leaguedashplayerptshot</td><td>leaguedashplayershotlocations</td><td>leaguedashplayerstats</td><td>leaguedashptdefend</td></tr><tr><td>leaguedashptstats</td><td>leaguedashptteamdefend</td><td>leaguedashteamclutch</td><td>leaguedashteamptshot</td></tr><tr><td>leaguedashteamshotlocations</td><td>leaguedashteamstats</td><td>leaguegamefinder</td><td>leaguegamelog</td></tr><tr><td>leagueleaders</td><td>leaguestandings</td><td>playbyplay</td><td>playbyplayv2</td></tr><tr><td>playerawards</td><td>playercareerstats</td><td>playercompare</td><td>playerdashboardbyclutch</td></tr><tr><td>playerdashboardbygamesplits</td><td>playerdashboardbygeneralsplits</td><td>playerdashboardbylastngames</td><td></td></tr><tr><td>playerdashboardbyshootingsplits</td><td>playerdashboardbyteamperformance</td><td>playerdashboardbyyearoveryear</td><td>playerdashptpass</td></tr><tr><td>playerdashptreb</td><td>playerdashptshotdefend</td><td>playerdashptshots</td><td>playerfantasyprofile</td></tr><tr><td>playerfantasyprofilebargraph</td><td>playergamelog</td><td>playergamestreakfinder</td><td>playernextngames</td></tr><tr><td>playerprofilev2</td><td>playersvsplayers</td><td>playervsplayer</td><td>playoffpicture</td></tr><tr><td>scoreboard</td><td>scoreboardv2</td><td>shotchartdetail</td><td>shotchartlineupdetail</td></tr><tr><td>teamdashboardbygeneralsplits</td><td></td><td></td><td></td></tr><tr><td></td><td>teamdashboardbyshootingsplits</td><td></td><td></td></tr><tr><td>teamdashlineups</td><td>teamdashptpass</td><td>teamdashptreb</td><td>teamdashptshots</td></tr><tr><td>teamdetails</td><td>teamgamelog</td><td>teamgamestreakfinder</td><td>teamhistoricalleaders</td></tr><tr><td>teaminfocommon</td><td>teamplayerdashboard</td><td>teamplayeronoffdetails</td><td>teamplayeronoffsummary</td></tr><tr><td>teamvsplayer</td><td>teamyearbyyearstats</td><td>videodetails</td><td>videoevents</td></tr><tr><td>videostatus</td></tr></table>

# %% [markdown]
# ### Getting Team and Player IDs
# The package also includes utilities for fetching player and team information available under `nba_api.stats.static`.
# You can use this to fetch player IDs and team IDs, which are often used as inputs to API endpoints.

# %%
from nba_api.stats.static import teams

# get_teams returns a list of 30 dictionaries, each an NBA team.
nba_teams = teams.get_teams()
print("Number of teams fetched: {}".format(len(nba_teams)))
nba_teams[:3]

# %%
from nba_api.stats.static import players

# get_players returns a list of dictionaries, each representing a player.
nba_players = players.get_players()
print("Number of players fetched: {}".format(len(nba_players)))
nba_players[:5]

# %% [markdown]
# To search for an individual team or player by its name (or other attribute), dictionary comprehensions are your friend.

# %%
spurs = [team for team in nba_teams if team["full_name"] == "San Antonio Spurs"][0]
spurs

# %%
big_fundamental = [
    player for player in nba_players if player["full_name"] == "Tim Duncan"
][0]
big_fundamental



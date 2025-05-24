#!/usr/bin/env python

"""
Improved Shot Charts Script for NBA API
This script fetches shot chart data for NBA players, handling common API issues and providing
better error handling and retry mechanisms.
"""

import pandas as pd
import numpy as np
import time
import requests
from requests.exceptions import RequestException
import sys
import argparse
from nba_api.stats.static import players
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import teams

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Fetch NBA shot chart data for players')
    parser.add_argument('--player', type=str, required=True, help='Full name of the player (e.g., "Stephen Curry")')
    parser.add_argument('--seasons', type=str, required=True, 
                      help='Comma-separated list of seasons (e.g., "2018-19,2019-20")')
    parser.add_argument('--shot_type', type=str, default='All', 
                      choices=['All', '3PT Field Goal', '2PT Field Goal'],
                      help='Type of shots to include (default: "All")')
    parser.add_argument('--output', type=str, default=None,
                      help='Output CSV file path (optional)')
    return parser.parse_args()

def get_player_id(player_name):
    """Find a player's ID from their name."""
    player_list = players.get_players()
    player_dict = [player for player in player_list if player['full_name'].lower() == player_name.lower()]
    
    if not player_dict:
        # Try a more flexible search if exact match fails
        player_dict = [player for player in player_list if player_name.lower() in player['full_name'].lower()]
    
    if player_dict:
        return player_dict[0]
    else:
        print(f"Error: Player '{player_name}' not found.")
        sys.exit(1)

def get_team_id(player_id, season):
    """Get team ID for a player in a given season."""
    career = playercareerstats.PlayerCareerStats(player_id=player_id)
    career_df = career.get_data_frames()[0]
    
    # Filter for the specified season
    season_stats = career_df[career_df['SEASON_ID'] == season]
    
    if not season_stats.empty:
        return season_stats['TEAM_ID'].iloc[0]
    else:
        # If no data for that season, use 0 to get all teams
        return 0

def get_shot_chart_data(player_id, team_id, season, season_type='Regular Season', retry_count=3, retry_delay=5):
    """Get shot chart data with retry mechanism."""
    headers = {
        'Host': 'stats.nba.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nba.com/',
        'x-nba-stats-origin': 'stats',
        'x-nba-stats-token': 'true'
    }
    
    # Set initial delay
    delay = retry_delay
    
    for attempt in range(retry_count):
        try:
            print(f"Fetching shot chart data for season {season} (attempt {attempt+1}/{retry_count})...")
            
            # Make the API call with all required parameters
            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=team_id,
                player_id=player_id,
                season_nullable=season,
                season_type_all_star=season_type,
                context_measure_simple='FGA',  # Use FGA to get both made and missed shots
                
                # Required parameters
                league_id='00',
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                game_segment_nullable='',
                date_from_nullable='',
                date_to_nullable='',
                location_nullable='',
                outcome_nullable='',
                player_position_nullable='',
                rookie_year_nullable='',
                season_segment_nullable='',
                vs_conference_nullable='',
                vs_division_nullable='',
                
                # Extra parameters
                headers=headers,
                timeout=60
            )
            
            # If we get here, request succeeded
            result = shot_chart.get_data_frames()
            
            if len(result) > 0 and not result[0].empty:
                return result[0]  # Return the shots data frame
            else:
                print(f"No shot data found for {season}.")
                return pd.DataFrame()  # Return empty dataframe
                
        except (RequestException, requests.exceptions.ConnectionError) as e:
            print(f"Error fetching data: {e}")
            if attempt < retry_count - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Maximum retries exceeded for season {season}.")
                return pd.DataFrame()  # Return empty dataframe

def filter_by_shot_type(df, shot_type):
    """Filter the dataframe by shot type."""
    if shot_type != 'All' and not df.empty:
        return df[df['SHOT_TYPE'] == shot_type]
    return df

def print_shot_summary(df, season):
    """Print summary statistics for the shots."""
    if df.empty:
        print(f"No data available for {season}")
        return
    
    total_shots = len(df)
    made_shots = df['SHOT_MADE_FLAG'].sum()
    
    print(f"\nSummary for {season}:")
    print(f"  Total shots: {total_shots}")
    print(f"  Made shots: {made_shots}")
    print(f"  FG%: {made_shots/total_shots:.3f}")
    
    # 3PT shots
    threes_df = df[df['SHOT_TYPE'] == '3PT Field Goal']
    if not threes_df.empty:
        total_threes = len(threes_df)
        made_threes = threes_df['SHOT_MADE_FLAG'].sum()
        print(f"  3PT shots: {total_threes}")
        print(f"  Made 3PT: {made_threes}")
        print(f"  3PT%: {made_threes/total_threes:.3f}")
    
    # 2PT shots
    twos_df = df[df['SHOT_TYPE'] == '2PT Field Goal']
    if not twos_df.empty:
        total_twos = len(twos_df)
        made_twos = twos_df['SHOT_MADE_FLAG'].sum()
        print(f"  2PT shots: {total_twos}")
        print(f"  Made 2PT: {made_twos}")
        print(f"  2PT%: {made_twos/total_twos:.3f}")

def main():
    args = parse_arguments()
    
    # Get player ID
    player = get_player_id(args.player)
    player_id = player['id']
    print(f"Found player: {player['full_name']} (ID: {player_id})")
    
    # Process each season
    seasons = [s.strip() for s in args.seasons.split(',')]
    all_shots_df = pd.DataFrame()
    
    for season in seasons:
        # Get team ID for the player in this season
        team_id = get_team_id(player_id, season)
        
        # Get shot chart data
        shots_df = get_shot_chart_data(player_id, team_id, season)
        
        # Filter by shot type if specified
        shots_df = filter_by_shot_type(shots_df, args.shot_type)
        
        # Print summary for this season
        print_shot_summary(shots_df, season)
        
        # Add to combined dataframe
        if not shots_df.empty:
            shots_df['SEASON'] = season  # Add season column
            all_shots_df = pd.concat([all_shots_df, shots_df])
    
    # Save to CSV if output path is specified
    if args.output and not all_shots_df.empty:
        all_shots_df.to_csv(args.output, index=False)
        print(f"\nData saved to {args.output}")
    
    # Print overall summary
    if not all_shots_df.empty:
        print("\nOverall summary:")
        total_shots = len(all_shots_df)
        made_shots = all_shots_df['SHOT_MADE_FLAG'].sum()
        
        print(f"Total shots across all seasons: {total_shots}")
        print(f"Made shots: {made_shots}")
        print(f"Overall FG%: {made_shots/total_shots:.3f}")
    else:
        print("No shot data found for any of the specified seasons.")
    
    return all_shots_df

if __name__ == "__main__":
    df = main()
    print("\nScript completed successfully!") 
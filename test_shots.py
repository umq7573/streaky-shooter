#!/usr/bin/env python

"""
Simple test script to verify ShotChartDetail API functionality
"""

from nba_api.stats.static import players
from nba_api.stats.endpoints import shotchartdetail
import pandas as pd
import time
import requests
from requests.exceptions import RequestException
import sys

def main():
    # Set up headers to mimic a browser request
    headers = {
        'Host': 'stats.nba.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nba.com/'
    }
    
    # Find player ID for Stephen Curry
    player = [p for p in players.get_players() if p['full_name'] == 'Stephen Curry'][0]
    player_id = player['id']
    print(f"Found player: {player['full_name']} (ID: {player_id})")
    
    # Get shot chart data with retry mechanism
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            print(f"Fetching shot chart data (attempt {attempt+1}/{max_retries})...")
            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=player_id,
                context_measure_simple='FGA',
                season_nullable='2019-20',
                season_type_all_star='Regular Season',
                
                # Required parameters based on documentation
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
                
                # Add headers and timeout
                headers=headers,
                timeout=60
            )
            
            # If we get here, the request succeeded
            shots_df = shot_chart.get_data_frames()[0]
            break
            
        except (RequestException, requests.exceptions.ConnectionError) as e:
            print(f"Error fetching data: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("Maximum retries exceeded. Exiting.")
                sys.exit(1)
    
    # Print summary
    total_shots = len(shots_df)
    made_shots = shots_df['SHOT_MADE_FLAG'].sum()
    print(f"Total shots: {total_shots}")
    print(f"Made shots: {made_shots}")
    print(f"FG%: {made_shots/total_shots:.3f}")
    
    # Filter for 3PT shots only
    threes_df = shots_df[shots_df['SHOT_TYPE'] == '3PT Field Goal']
    total_threes = len(threes_df)
    made_threes = threes_df['SHOT_MADE_FLAG'].sum()
    print(f"\n3PT shots: {total_threes}")
    print(f"Made 3PT: {made_threes}")
    print(f"3PT%: {made_threes/total_threes:.3f}")
    
    return shots_df

if __name__ == "__main__":
    shots_df = main()
    print("\nScript completed successfully!") 
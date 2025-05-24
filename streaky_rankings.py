#!/usr/bin/env python

"""
Streaky Rankings - Analyze the NBA's streakiest shooters by minutes played

This script finds the top N players by minutes played across specified seasons,
then ranks them by streakiness using the momentum score metric.
"""

import pandas as pd
import numpy as np
import time
import requests
from requests.exceptions import RequestException
import sys
import argparse
from tqdm import tqdm
from nba_api.stats.static import players
from nba_api.stats.endpoints import shotchartdetail, leagueleaders, playercareerstats
from nba_api.stats.library.parameters import SeasonTypeAllStar

# Import the momentum_score function from streaky.py
from streaky import momentum_score, get_headers


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze streakiness of top NBA shooters')
    parser.add_argument('--seasons', type=str, required=True,
                      help='Comma-separated list of seasons (e.g., "2018-19,2019-20")')
    parser.add_argument('--top_n', type=int, default=50,
                      help='Number of top players to analyze (default: 50)')
    parser.add_argument('--min_shots', type=int, default=200,
                      help='Minimum number of shots required for analysis (default: 200)')
    parser.add_argument('--shot_type', type=str, default='3PT Field Goal',
                      choices=['All', '3PT Field Goal', '2PT Field Goal'],
                      help='Type of shots to analyze (default: "3PT Field Goal")')
    parser.add_argument('--rho', type=float, default=0.9,
                      help='Persistence factor for momentum score (default: 0.9)')
    parser.add_argument('--penalty', type=float, default=0.1,
                      help='Penalty scale for momentum score (default: 0.1)')
    parser.add_argument('--output', type=str, default=None,
                      help='Output CSV file path for full results (optional)')
    return parser.parse_args()


def get_players_by_minutes(season, season_type="Regular Season", headers=None):
    """Get players and their minutes for a given season."""
    headers = headers or get_headers()
    
    # Map season type to the parameter expected by the API
    season_type_map = {
        "Regular Season": SeasonTypeAllStar.regular,
        "Playoffs": SeasonTypeAllStar.playoffs,
        "All Star": SeasonTypeAllStar.all_star,
        "Pre Season": SeasonTypeAllStar.preseason
    }
    
    season_type_param = season_type_map.get(season_type, SeasonTypeAllStar.regular)
    
    # Get league leaders in minutes played
    leaders = leagueleaders.LeagueLeaders(
        season=season,
        season_type_all_star=season_type_param,
        stat_category_abbreviation='MIN',
        headers=headers
    )
    
    # Get the data frame with player minutes
    leaders_df = leaders.get_data_frames()[0]
    
    # Just return all players with their minutes
    return leaders_df[['PLAYER_ID', 'PLAYER', 'MIN']]


def get_top_players_across_seasons(seasons, season_type="Regular Season", top_n=50):
    """Get the top N players by total minutes across all specified seasons."""
    print(f"Gathering minutes played data across {len(seasons)} seasons...")
    
    all_players_minutes = []
    headers = get_headers()
    
    for i, season in enumerate(seasons):
        print(f"Getting player minutes for season {season}...")
        
        # Get minutes for all players in this season
        season_minutes = get_players_by_minutes(season, season_type, headers)
        
        # Add season column for reference
        season_minutes['SEASON'] = season
        
        # Add to our list
        all_players_minutes.append(season_minutes)
        
        # Sleep between API calls to avoid rate limiting
        if i < len(seasons) - 1:  # Don't sleep after the last season
            print("Waiting to avoid rate limiting...")
            time.sleep(0.8)
    
    # Combine all seasons' data
    combined_minutes = pd.concat(all_players_minutes)
    
    # Group by player and sum their minutes across seasons
    player_total_minutes = combined_minutes.groupby(['PLAYER_ID', 'PLAYER'])['MIN'].sum().reset_index()
    
    # Sort by total minutes (descending) and take top N
    top_players = player_total_minutes.sort_values('MIN', ascending=False).head(top_n)
    
    return top_players


def get_team_id(player_id, season):
    """Get team ID for a player in a given season."""
    try:
        # Add longer timeout and retry mechanism for career stats
        for attempt in range(3):  # 3 retries
            try:
                career = playercareerstats.PlayerCareerStats(
                    player_id=player_id,
                    timeout=90,  # Longer timeout
                    headers=get_headers()
                )
                career_df = career.get_data_frames()[0]
                
                # Filter for the specified season
                season_stats = career_df[career_df['SEASON_ID'] == season]
                
                if not season_stats.empty:
                    return season_stats['TEAM_ID'].iloc[0]
                
                break  # Success, exit retry loop
                
            except Exception as e:
                print(f"Error getting career stats for player {player_id}, attempt {attempt+1}/3: {e}")
                if attempt < 2:  # Last attempt doesn't need to sleep
                    time.sleep(10 * (attempt + 1))  # Increasing sleep time for each retry
        
    except Exception as e:
        print(f"Warning: Could not get team ID for player {player_id} in season {season}: {e}")
    
    # If no data for that season or any error, use 0 to get all teams
    return 0


def get_shot_chart_data(player_id, team_id, season, season_type='Regular Season', 
                       shot_type='All', retry_count=3, retry_delay=5):
    """Get shot chart data with retry mechanism."""
    headers = get_headers()
    
    # Set initial delay
    delay = retry_delay
    
    for attempt in range(retry_count):
        try:
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
                timeout=90  # Longer timeout
            )
            
            # If we get here, request succeeded
            result = shot_chart.get_data_frames()
            
            if len(result) > 0 and not result[0].empty:
                df = result[0]
                # Filter by shot type if specified
                if shot_type != 'All':
                    df = df[df['SHOT_TYPE'] == shot_type]
                return df
            else:
                return pd.DataFrame()  # Return empty dataframe
                
        except (RequestException, requests.exceptions.ConnectionError) as e:
            if attempt < retry_count - 1:
                print(f"Error fetching data: {e}, retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Maximum retries exceeded for player {player_id} in season {season}.")
                return pd.DataFrame()  # Return empty dataframe
        
        # Add delay between attempts (even after success)
        time.sleep(3)  # Increased delay to avoid hitting rate limits
    
    return pd.DataFrame()  # Default return if all attempts fail


def analyze_players(top_players_df, seasons, shot_type, rho, penalty, min_shots):
    """Analyze shooting streakiness for a list of players across specified seasons."""
    results = []
    
    # Prepare progress bar
    total_analyses = len(top_players_df)
    with tqdm(total=total_analyses, desc="Analyzing players") as pbar:
        for _, player in top_players_df.iterrows():
            player_id = player['PLAYER_ID']
            player_name = player['PLAYER']
            
            try:
                # Get shots from all seasons
                all_shots = []
                
                for season in seasons:
                    # Get team ID
                    team_id = get_team_id(player_id, season)
                    
                    # Add delay between API calls to avoid rate limiting
                    time.sleep(0.8)
                    
                    # Get shot chart data
                    shots_df = get_shot_chart_data(
                        player_id=player_id, 
                        team_id=team_id, 
                        season=season,
                        shot_type=shot_type
                    )
                    
                    if not shots_df.empty:
                        shots = shots_df.sort_values(["GAME_DATE", "GAME_ID", "GAME_EVENT_ID"])["SHOT_MADE_FLAG"]
                        all_shots.append(shots)
                    
                    # Add delay between processing different seasons for the same player
                    time.sleep(0.8)
                
                # Combine shots from all seasons
                if all_shots:
                    all_shots_series = pd.concat(all_shots).reset_index(drop=True)
                    
                    # Only analyze if we have enough shots
                    if len(all_shots_series) >= min_shots:
                        # Calculate the momentum score
                        score = momentum_score(all_shots_series.to_numpy(), rho, penalty)
                        
                        # Collect results
                        results.append({
                            'PLAYER_ID': player_id,
                            'PLAYER_NAME': player_name,
                            'TOTAL_MIN': player['MIN'],
                            'SHOTS': len(all_shots_series),
                            'MADE': int(all_shots_series.sum()),
                            'FG_PCT': round(all_shots_series.mean(), 3),
                            'MOMENTUM_SCORE': round(score, 3)
                        })
                    else:
                        print(f"Skipping {player_name}: Only {len(all_shots_series)} shots (minimum {min_shots} required)")
                else:
                    print(f"Skipping {player_name}: No shots found")
            
            except Exception as e:
                print(f"Error analyzing {player_name}: {e}")
            
            finally:
                # Update progress bar
                pbar.update(1)
                
                # Add delay between players to avoid rate limiting
                time.sleep(0.8)
    
    # Convert to DataFrame and sort by score
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values('MOMENTUM_SCORE', ascending=False).reset_index(drop=True)
    
    return results_df


def main():
    args = parse_arguments()
    
    # Process seasons
    seasons = [s.strip() for s in args.seasons.split(',')]
    
    # Get top players by total minutes across all specified seasons
    top_players = get_top_players_across_seasons(seasons, top_n=args.top_n)
    
    print(f"\nFound the top {len(top_players)} players by total minutes across {len(seasons)} seasons.")
    print("Top 5 players by minutes:")
    for _, player in top_players.head(5).iterrows():
        print(f"  {player['PLAYER']}: {player['MIN']} minutes")
    
    # Analyze players
    print(f"\nAnalyzing these {args.top_n} players for streakiness in {args.shot_type} shots...")
    results = analyze_players(
        top_players, 
        seasons, 
        args.shot_type, 
        args.rho, 
        args.penalty,
        args.min_shots
    )
    
    # Display results
    if not results.empty:
        # Add ranking column
        results['RANK'] = range(1, len(results) + 1)
        
        # Display top 20 streakiest shooters (or all if fewer)
        display_count = min(20, len(results))
        print(f"\nTop {display_count} Streakiest Shooters:")
        top_results = results.head(display_count)
        display_cols = ['RANK', 'PLAYER_NAME', 'SHOTS', 'MADE', 'FG_PCT', 'MOMENTUM_SCORE']
        print(top_results[display_cols].to_string(index=False))
        
        # Save full results to CSV if specified
        if args.output:
            results.to_csv(args.output, index=False)
            print(f"\nFull results saved to {args.output}")
            
        # Additional statistics
        print("\nStatistics on Momentum Scores:")
        print(f"Mean: {results['MOMENTUM_SCORE'].mean():.3f}")
        print(f"Median: {results['MOMENTUM_SCORE'].median():.3f}")
        print(f"Min: {results['MOMENTUM_SCORE'].min():.3f}")
        print(f"Max: {results['MOMENTUM_SCORE'].max():.3f}")
        
        # Number of players analyzed
        print(f"\nAnalyzed {len(results)} players with at least {args.min_shots} {args.shot_type} shots across {len(seasons)} seasons.")
        print(f"({len(top_players) - len(results)} players were skipped due to insufficient shot data)")
        
        return results
    else:
        print("No results found. Try adjusting parameters.")
        return pd.DataFrame()


if __name__ == "__main__":
    results_df = main()
    print("\nAnalysis completed successfully!") 
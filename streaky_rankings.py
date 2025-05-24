#!/usr/bin/env python

"""
Streaky Rankings - Analyze the NBA's streakiest shooters by minutes played

This script finds the top N players by minutes played across specified seasons,
then ranks them by streakiness using the run-based streakiness index S.
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

# Import the streakiness functions from streaky.py
from streaky import run_based_streakiness, momentum_score, get_headers

# Interactive and enhanced output imports
try:
    import questionary
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    INTERACTIVE_AVAILABLE = True
except ImportError:
    INTERACTIVE_AVAILABLE = False

console = Console() if 'Console' in globals() else None


def get_current_season():
    """Get the current NBA season string."""
    from datetime import datetime
    year = datetime.now().year
    month = datetime.now().month
    
    # NBA season runs roughly October to June
    if month >= 10:  # October-December
        return f"{year}-{str(year + 1)[2:]}"
    else:  # January-September
        return f"{year - 1}-{str(year)[2:]}"


def interactive_setup():
    """Interactive setup for analysis parameters."""
    if not INTERACTIVE_AVAILABLE:
        console.print("❌ Interactive mode requires 'questionary' and 'rich'")
        console.print("📦 Install with: pip install questionary rich")
        sys.exit(1)
    
    # Welcome message
    console.print(Panel.fit(
        "[bold blue]🏀 NBA Streakiness Analysis[/bold blue]\n"
        "Analyze the streakiest shooters by minutes played\n"
        "[dim]Press Ctrl+C anytime to exit[/dim]",
        border_style="blue"
    ))
    
    try:
        # Season selection
        recent_seasons = [
            f"{year}-{str(year + 1)[2:]}" 
            for year in range(2024, 2018, -1)  # 2024-25 down to 2019-20
        ]
        
        console.print("\n[bold]Season Selection[/bold]")
        console.print("[dim]Use arrow keys to navigate, SPACE to select/deselect, ENTER to confirm[/dim]")
        
        # Create choices including older seasons option
        season_choices = [
            questionary.Choice(season, checked=(season == get_current_season()))
            for season in recent_seasons
        ]
        season_choices.append(questionary.Choice("➕ Add older seasons", value="add_older"))
        
        selected_items = questionary.checkbox(
            "Select seasons to analyze:",
            choices=season_choices
        ).ask()
        
        # Filter out the "add older seasons" option and get actual seasons
        selected_seasons = [item for item in selected_items if item != "add_older"]
        
        # If user selected to add older seasons, ask for them
        if "add_older" in selected_items:
            custom_seasons = questionary.text(
                "Enter additional seasons (comma-separated, e.g. '2017-18,2016-17'):",
                validate=lambda x: all(len(s.strip()) == 7 and '-' in s for s in x.split(',')) if x.strip() else True
            ).ask()
            if custom_seasons.strip():
                selected_seasons.extend([s.strip() for s in custom_seasons.split(',')])
        
        if not selected_seasons:
            console.print("❌ No seasons selected")
            sys.exit(1)
        
        # Number of players
        console.print("\n[bold]Analysis Scope[/bold]")
        top_n = int(questionary.text(
            "Number of top players to analyze:",
            default="50",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 500
        ).ask())
        
        # Minimum shots
        min_shots = int(questionary.text(
            "Minimum shots required per player:",
            default="200",
            validate=lambda x: x.isdigit() and int(x) > 0
        ).ask())
        
        # Shot type
        console.print("[dim]Use arrow keys to navigate, ENTER to select[/dim]")
        shot_type = questionary.select(
            "Shot type to analyze:",
            choices=[
                "3PT Field Goal",
                "2PT Field Goal", 
                "All"
            ],
            default="3PT Field Goal"
        ).ask()
        
        # Metric
        console.print("[dim]Use arrow keys to navigate, ENTER to select[/dim]")
        metric = questionary.select(
            "Streakiness metric:",
            choices=[
                questionary.Choice("Run-based index S (recommended)", value="run"),
                questionary.Choice("Legacy momentum score", value="momentum")
            ],
            default="run"
        ).ask()
        
        # Output file
        save_results = questionary.confirm("Save results to CSV file?", default=True).ask()
        output_file = None
        if save_results:
            default_filename = f"streaky_results_{'_'.join(selected_seasons)}.csv"
            output_file = questionary.text(
                "Output filename:",
                default=default_filename
            ).ask()
        
        return {
            'seasons': selected_seasons,
            'top_n': top_n,
            'min_shots': min_shots,
            'shot_type': shot_type,
            'metric': metric,
            'output': output_file
        }
        
    except (KeyboardInterrupt, EOFError):
        console.print("\n👋 Analysis cancelled")
        sys.exit(0)


def enhanced_display_results(results_df, config):
    """Display results with rich formatting."""
    if console is None:
        # Fallback to regular display if rich not available
        print(f"\nAll {len(results_df)} Streakiest Shooters:")
        if config['metric'] == 'run':
            score_col = 'STREAKINESS_S'
            print("(Lower S = more streaky)")
        else:
            score_col = 'MOMENTUM_SCORE'
            print("(Higher momentum = more streaky)")
        
        display_cols = ['RANK', 'PLAYER_NAME', 'SHOTS', 'MADE', 'FG_PCT', score_col]
        print(results_df[display_cols].to_string(index=False))
        return
    
    # Rich display
    score_col = 'STREAKINESS_S' if config['metric'] == 'run' else 'MOMENTUM_SCORE'
    
    # Create title
    title_text = "🏀 NBA Streakiness Rankings"
    if config['metric'] == 'run':
        subtitle = f"All {len(results_df)} players by Run-based Index S (lower = more streaky)"
    else:
        subtitle = f"All {len(results_df)} players by Momentum Score (higher = more streaky)"
    
    # Create table
    table = Table(title=title_text, show_header=True, header_style="bold magenta")
    # Add subtitle as caption instead
    table.caption = subtitle
    table.add_column("Rank", style="cyan", justify="center", width=6)
    table.add_column("Player", style="white", width=20)
    table.add_column("Shots", style="green", justify="right", width=8)
    table.add_column("Made", style="green", justify="right", width=8)
    table.add_column("FG%", style="yellow", justify="right", width=8)
    table.add_column("Score", style="red bold", justify="right", width=10)
    
    # Add rows (all of them)
    for _, row in results_df.iterrows():
        table.add_row(
            str(int(row['RANK'])),
            row['PLAYER_NAME'][:19],  # Truncate long names
            str(row['SHOTS']),
            str(row['MADE']),
            str(row['FG_PCT']),
            str(row[score_col])
        )
    
    console.print("\n")
    console.print(table)
    
    # Summary statistics
    stats_panel = Panel(
        f"[bold]Analysis Summary[/bold]\n"
        f"Players analyzed: {len(results_df)}\n"
        f"Seasons: {', '.join(config['seasons'])}\n" 
        f"Shot type: {config['shot_type']}\n"
        f"Min shots: {config['min_shots']}\n"
        f"Mean score: {results_df[score_col].mean():.3f}\n"
        f"Score range: {results_df[score_col].min():.3f} - {results_df[score_col].max():.3f}",
        title="📊 Statistics",
        border_style="green"
    )
    console.print(stats_panel)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze streakiness of top NBA shooters')
    parser.add_argument('--interactive', '-i', action='store_true',
                      help='Launch interactive mode (default if no other args provided)')
    parser.add_argument('--seasons', type=str,
                      help='Comma-separated list of seasons (e.g., "2018-19,2019-20")')
    parser.add_argument('--top_n', type=int, default=50,
                      help='Number of top players to analyze (default: 50)')
    parser.add_argument('--min_shots', type=int, default=200,
                      help='Minimum number of shots required for analysis (default: 200)')
    parser.add_argument('--shot_type', type=str, default='3PT Field Goal',
                      choices=['All', '3PT Field Goal', '2PT Field Goal'],
                      help='Type of shots to analyze (default: "3PT Field Goal")')
    parser.add_argument('--metric', type=str, default='run', choices=['run', 'momentum'],
                      help='Streakiness metric to use: "run" (default) or "momentum" (legacy)')
    parser.add_argument('--rho', type=float, default=0.9,
                      help='Persistence factor for momentum metric (ignored for run metric, default: 0.9)')
    parser.add_argument('--penalty', type=float, default=0.1,
                      help='Penalty scale for momentum metric (ignored for run metric, default: 0.1)')
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


def analyze_players(top_players_df, seasons, shot_type, metric, rho, penalty, min_shots):
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
                        # Calculate the streakiness score based on chosen metric
                        if metric == 'run':
                            score = run_based_streakiness(all_shots_series.to_numpy())
                            score_column = 'STREAKINESS_S'
                        else:  # momentum
                            score = momentum_score(all_shots_series.to_numpy(), rho, penalty)
                            score_column = 'MOMENTUM_SCORE'
                        
                        # Collect results
                        result_dict = {
                            'PLAYER_ID': player_id,
                            'PLAYER_NAME': player_name,
                            'TOTAL_MIN': player['MIN'],
                            'SHOTS': len(all_shots_series),
                            'MADE': int(all_shots_series.sum()),
                            'FG_PCT': round(all_shots_series.mean(), 3),
                            score_column: round(score, 3)
                        }
                        results.append(result_dict)
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
        if metric == 'run':
            # For run-based metric, lower scores are more streaky
            results_df = results_df.sort_values('STREAKINESS_S', ascending=True).reset_index(drop=True)
        else:
            # For momentum metric, higher scores are more streaky
            results_df = results_df.sort_values('MOMENTUM_SCORE', ascending=False).reset_index(drop=True)
    
    return results_df


def main():
    args = parse_arguments()
    
    # Determine if we should use interactive mode
    use_interactive = args.interactive or (len(sys.argv) == 1 and INTERACTIVE_AVAILABLE)
    
    if use_interactive:
        config = interactive_setup()
        seasons = config['seasons']
        # Convert config to args-like object for compatibility
        args.top_n = config['top_n']
        args.min_shots = config['min_shots']
        args.shot_type = config['shot_type']
        args.metric = config['metric']
        args.output = config['output']
        args.rho = 0.9  # Default values for interactive mode
        args.penalty = 0.1
    else:
        if not args.seasons:
            print("Error: --seasons is required when not using interactive mode")
            print("Use --interactive or -i for guided setup")
            sys.exit(1)
        seasons = [s.strip() for s in args.seasons.split(',')]
        config = {
            'seasons': seasons,
            'top_n': args.top_n,
            'min_shots': args.min_shots,
            'shot_type': args.shot_type,
            'metric': args.metric,
            'output': args.output
        }
    
    # Get top players by total minutes across all specified seasons
    top_players = get_top_players_across_seasons(seasons, top_n=args.top_n)
    
    print(f"\nFound the top {len(top_players)} players by total minutes across {len(seasons)} seasons.")
    print("Top 5 players by minutes:")
    for _, player in top_players.head(5).iterrows():
        print(f"  {player['PLAYER']}: {player['MIN']} minutes")
    
    # Analyze players
    metric_name = "run-based streakiness index S" if args.metric == 'run' else "momentum score"
    print(f"\nAnalyzing these {args.top_n} players for {metric_name} in {args.shot_type} shots...")
    results = analyze_players(
        top_players, 
        seasons, 
        args.shot_type, 
        args.metric,
        args.rho, 
        args.penalty,
        args.min_shots
    )
    
    # Display results
    if not results.empty:
        # Add ranking column
        results['RANK'] = range(1, len(results) + 1)
        
        # Use enhanced display if available, otherwise fallback
        if use_interactive and console:
            enhanced_display_results(results, config)
        else:
            # Original display logic
            
            if args.metric == 'run':
                print(f"\nAll {len(results)} Streakiest Shooters (by S index, lower = more streaky):")
                score_col = 'STREAKINESS_S'
            else:
                print(f"\nAll {len(results)} Streakiest Shooters (by momentum score, higher = more streaky):")
                score_col = 'MOMENTUM_SCORE'
                
            display_cols = ['RANK', 'PLAYER_NAME', 'SHOTS', 'MADE', 'FG_PCT', score_col]
            print(results[display_cols].to_string(index=False))
            
            # Additional statistics
            print(f"\nStatistics on {metric_name}:")
            print(f"Mean: {results[score_col].mean():.3f}")
            print(f"Median: {results[score_col].median():.3f}")
            print(f"Min: {results[score_col].min():.3f}")
            print(f"Max: {results[score_col].max():.3f}")
        
        # Save full results to CSV if specified
        if args.output:
            results.to_csv(args.output, index=False)
            if console:
                console.print(f"\n✅ Full results saved to: {args.output}")
            else:
                print(f"\nFull results saved to {args.output}")
            
        # Number of players analyzed
        print(f"\nAnalyzed {len(results)} players with at least {args.min_shots} {args.shot_type} shots across {len(seasons)} seasons.")
        print(f"({len(top_players) - len(results)} players were skipped due to insufficient shot data)")
        
        return results
    else:
        print("No results found. Try adjusting parameters.")
        return pd.DataFrame()


if __name__ == "__main__":
    results_df = main()
    if console:
        console.print("\n🎉 Analysis completed successfully!")
    else:
        print("\nAnalysis completed successfully!") 
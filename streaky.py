#!/usr/bin/env python
"""
streaky.py  –  pull NBA shot data and compute streakiness metrics
               in one script.

Dependencies
------------
pip install nba_api pandas numpy tqdm
"""

import time, argparse, sys
import numpy as np
import pandas as pd
from tqdm import tqdm
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats
import requests
from requests.exceptions import RequestException


# ----------------------------------------------------------------------
# Helper functions for run-based streakiness
# ----------------------------------------------------------------------
def _r_min(k: int, n: int) -> int:
    """
    Minimum possible number of runs for k makes out of n shots.
    
    Args:
        k: Number of makes
        n: Total number of shots
        
    Returns:
        Minimum number of runs
    """
    if k == 0 or k == n:
        return 1  # All misses or all makes = 1 run
    return 2  # All makes together, then all misses together (or vice versa)


def _r_max(k: int, n: int) -> int:
    """
    Maximum possible number of runs for k makes out of n shots.
    
    Args:
        k: Number of makes
        n: Total number of shots
        
    Returns:
        Maximum number of runs
    """
    if k == 0 or k == n:
        return 1  # All misses or all makes = 1 run
    
    # Compact formula: R_max = 2 * min(k, n-k) + 1_{k ≠ n-k}
    # The indicator function adds 1 when unbalanced (dangling majority block)
    return 2 * min(k, n - k) + int(k != n - k)


def _count_runs(flags: np.ndarray) -> int:
    """
    Count the number of runs in a binary sequence using vectorized operations.
    
    Args:
        flags: Binary array of 0s and 1s
        
    Returns:
        Number of runs in the sequence
    """
    if len(flags) <= 1:
        return 1
    
    # Use np.diff to find where values change, then count transitions + 1
    transitions = np.sum(np.diff(flags) != 0)
    return transitions + 1


def run_based_streakiness(flags: np.ndarray) -> float:
    """
    Compute the run-based streakiness index S.
    
    S = (R - R_min) / (R_max - R_min)
    
    Where:
    - R is the actual number of runs
    - R_max is the maximum possible runs for this make/miss distribution
    - R_min is the minimum possible runs for this make/miss distribution
    
    Args:
        flags: 0/1 array of SHOT_MADE_FLAG in chronological order
        
    Returns:
        Streakiness index S in range [0, 1], where 0 = most streaky, 1 = most random
    """
    if flags.size <= 1:
        return 0.0  # Degenerate case
    
    n = len(flags)
    k = int(flags.sum())  # Number of makes
    
    # Handle degenerate cases
    if k == 0 or k == n:
        return 0.0  # All makes or all misses = perfectly streaky
    
    # Count actual runs
    r_actual = _count_runs(flags)
    
    # Compute theoretical bounds
    r_min = _r_min(k, n)
    r_max = _r_max(k, n)
    
    # Handle edge case where r_min == r_max
    if r_max == r_min:
        return 0.0
    
    # Compute streakiness index (corrected formula)
    s = (r_actual - r_min) / (r_max - r_min)
    
    # Ensure result is in [0, 1] range
    return max(0.0, min(1.0, s))


# ----------------------------------------------------------------------
# Legacy momentum score (for backward compatibility)
# ----------------------------------------------------------------------
def momentum_score(flags: np.ndarray,
                   rho: float = 0.9,
                   penalty_scale: float = 0.1) -> float:
    """
    Legacy momentum-based streakiness metric.
    
    flags : 0/1 array of SHOT_MADE_FLAG in chronological order.
    rho   : persistence factor (0–1). Higher = longer memory.
    penalty_scale : extra kick when the shot flips momentum's sign.

    Returns: mean absolute momentum (higher ⇒ streakier).
    """
    if flags.size == 0:
        return 0.0

    p = flags.mean()
    if p in (0.0, 1.0):
        return 0.0                                   # degenerate

    sigma = np.sqrt(p * (1 - p))
    M, acc = 0.0, 0.0

    for x in flags:
        step = (x - p) / sigma                       # ±1/σ centred
        future = rho * M + step

        if np.sign(future) != np.sign(M) and M != 0:
            future -= penalty_scale * np.sign(M)     # snap-back

        M = future
        acc += abs(M)

    return acc / flags.size


# ----------------------------------------------------------------------
# Data pull helpers
# ----------------------------------------------------------------------
def get_headers():
    """Return headers for NBA API requests."""
    return {
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

def get_player_id(name: str) -> int:
    """Get a player's ID from their full name."""
    try:
        hit = next(p for p in players.get_players() if p["full_name"].lower() == name.lower())
        return hit["id"]
    except StopIteration:
        # Try a more flexible search
        matches = [p for p in players.get_players() if name.lower() in p["full_name"].lower()]
        if matches:
            print(f"Found player {matches[0]['full_name']} as closest match.")
            return matches[0]["id"]
        else:
            print(f"Error: Player '{name}' not found.")
            sys.exit(1)

def get_team_id(player_id: int, season: str) -> int:
    """Get team ID for a player in a given season."""
    try:
        career = playercareerstats.PlayerCareerStats(player_id=player_id)
        career_df = career.get_data_frames()[0]
        
        # Filter for the specified season
        season_stats = career_df[career_df['SEASON_ID'] == season]
        
        if not season_stats.empty:
            return season_stats['TEAM_ID'].iloc[0]
    except Exception as e:
        print(f"Warning: Could not get team ID for player {player_id} in season {season}: {e}")
    
    # If no data for that season or any error, use 0 to get all teams
    return 0

def fetch_shots(pid: int,
                season: str,
                shot_type: str = "All",
                season_type: str = "Regular Season",
                delay: float = 0.6,
                max_retries: int = 3) -> pd.Series:
    """Return SHOT_MADE_FLAG series ordered by time."""
    headers = get_headers()
    team_id = get_team_id(pid, season)
    
    # Set initial delay
    retry_delay = delay
    
    for attempt in range(max_retries):
        try:
            print(f"Fetching data for player {pid}, season {season} (attempt {attempt+1}/{max_retries})...")
            
            rsp = shotchartdetail.ShotChartDetail(
                team_id=team_id,
                player_id=pid,
                season_nullable=season,
                season_type_all_star=season_type,
                context_measure_simple="FGA",  # Use FGA to get both made and missed shots
                
                # Required parameters
                league_id="00",
                last_n_games=0,
                month=0,
                opponent_team_id=0,
                period=0,
                game_segment_nullable="",
                date_from_nullable="",
                date_to_nullable="",
                location_nullable="",
                outcome_nullable="",
                player_position_nullable="",
                rookie_year_nullable="",
                season_segment_nullable="",
                vs_conference_nullable="",
                vs_division_nullable="",
                
                # Extra parameters
                headers=headers,
                timeout=60
            )
            
            df = rsp.get_data_frames()[0]
            
            if shot_type != "All":
                df = df[df["SHOT_TYPE"] == shot_type]
                
            # Check if we have any data
            if df.empty:
                print(f"No shot data found for player {pid} in season {season} with shot type {shot_type}")
                return pd.Series(dtype=np.int8)  # Return empty series
                
            out = (df.sort_values(["GAME_DATE", "GAME_ID", "GAME_EVENT_ID"])
                    .reset_index(drop=True)["SHOT_MADE_FLAG"]
                    .astype(np.int8))
                    
            print(f"Retrieved {len(out)} shots for player {pid} in season {season}")
            time.sleep(delay)
            return out
            
        except (RequestException, requests.exceptions.ConnectionError) as e:
            print(f"Error fetching data: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Maximum retries exceeded for player {pid} in season {season}")
                return pd.Series(dtype=np.int8)  # Return empty series

# ----------------------------------------------------------------------
# CLI glue
# ----------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Compute shooting streakiness metrics")
    ap.add_argument("--players", required=True,
                    help="Comma-separated full names (e.g. 'Stephen Curry,Klay Thompson')")
    ap.add_argument("--seasons", required=True,
                    help="Comma-separated seasons (e.g. '2019-20,2020-21')")
    ap.add_argument("--metric", default="run", choices=["run", "momentum"],
                    help="Streakiness metric to use: 'run' (default) or 'momentum' (legacy)")
    ap.add_argument("--rho", type=float, default=0.9,
                    help="Persistence factor for momentum metric (ignored for run metric)")
    ap.add_argument("--penalty", type=float, default=0.1,
                    help="Penalty scale for momentum metric (ignored for run metric)")
    ap.add_argument("--shot_type", default="All",
                    choices=["All", "3PT Field Goal", "2PT Field Goal"])
    ap.add_argument("--max_retries", type=int, default=3,
                    help="Maximum number of retries for API calls")
    ap.add_argument("--delay", type=float, default=0.6,
                    help="Delay between API calls in seconds")
    args = ap.parse_args(argv)

    names = [n.strip() for n in args.players.split(",") if n.strip()]
    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]

    rows = []
    for name in tqdm(names, desc="Players"):
        try:
            pid = get_player_id(name)
            
            # Collect shots for all specified seasons
            all_shots = []
            for season in seasons:
                shots = fetch_shots(
                    pid=pid, 
                    season=season, 
                    shot_type=args.shot_type,
                    max_retries=args.max_retries,
                    delay=args.delay
                )
                all_shots.append(shots)
            
            # Combine all shots
            flags = pd.concat(all_shots)
            
            # Skip if no shots were found
            if flags.empty:
                print(f"No shots found for {name}, skipping...")
                continue
                
            # Calculate the streakiness score based on chosen metric
            if args.metric == "run":
                score = run_based_streakiness(flags.to_numpy())
                score_label = "S"
            else:  # momentum
                score = momentum_score(flags.to_numpy(), args.rho, args.penalty)
                score_label = "momentum"
            
            rows.append({
                "player": name,
                "shots": int(flags.size),
                "metric": score_label,
                "score": round(score, 3)
            })
            
        except Exception as e:
            print(f"Error processing {name}: {e}")

    if not rows:
        print("No data found for any player. Check parameters and try again.")
        return

    df = pd.DataFrame(rows)
    if args.metric == "run":
        df = df.sort_values("score", ascending=True)  # Lower S = more streaky
        print("Results (sorted by streakiness index S, lower = more streaky):")
    else:
        df = df.sort_values("score", ascending=False)  # Higher momentum = more streaky
        print("Results (sorted by momentum score, higher = more streaky):")
    
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

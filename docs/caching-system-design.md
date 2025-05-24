# NBA API Data Caching System Design

## Overview

This document outlines the design for implementing a comprehensive caching system for the NBA Streaky Shooter project to reduce API calls, improve performance, and enhance reliability.

## Current API Usage Analysis

### Primary Data Sources

1. **ShotChartDetail** (most frequent)
   - Used in: `fetch_shots()`, `get_shot_chart_data()`
   - Parameters: player_id, team_id, season, shot_type, season_type
   - Data: Individual shot records with timestamps, coordinates, make/miss flags
   - Call frequency: ~1-2 calls per player per season

2. **LeagueLeaders** 
   - Used in: `get_players_by_minutes()`
   - Parameters: season, season_type, stat_category
   - Data: Player rankings by minutes played
   - Call frequency: 1 call per season

3. **PlayerCareerStats**
   - Used in: `get_team_id()`
   - Parameters: player_id
   - Data: Career statistics to determine team affiliations
   - Call frequency: 1 call per player (across all analyses)

### Performance Pain Points

- **Rate Limiting**: Current delays of 0.6-0.8s between calls
- **Repeated Requests**: Same data fetched multiple times across runs
- **Reliability**: Network errors require retries and exponential backoff
- **Analysis Time**: Large-scale analyses take 10-30+ minutes

## Proposed Caching Architecture

### 1. Storage Strategy

**JSON-based hierarchical storage** with the following structure:

```
data/cache/
├── shot_charts/
│   ├── player_203897/           # Player ID
│   │   ├── 2023-24_3PT.json     # Season_ShotType
│   │   ├── 2023-24_All.json
│   │   └── 2022-23_3PT.json
│   └── player_1628983/
├── league_leaders/
│   ├── 2023-24_MIN.json         # Season_StatCategory
│   └── 2022-23_MIN.json
├── career_stats/
│   ├── player_203897.json       # Player career data
│   └── player_1628983.json
└── metadata.json                # Cache metadata and timestamps
```

### 2. Cache Key Generation

**Hierarchical key system** based on API endpoint and parameters:

```python
# ShotChartDetail
key = f"shot_charts/player_{player_id}/{season}_{shot_type}.json"

# LeagueLeaders  
key = f"league_leaders/{season}_{stat_category}.json"

# PlayerCareerStats
key = f"career_stats/player_{player_id}.json"
```

### 3. Cache Manager Implementation

```python
class NBADataCache:
    def __init__(self, cache_dir="data/cache", max_age_days=7):
        self.cache_dir = Path(cache_dir)
        self.max_age_days = max_age_days
        self.metadata = self._load_metadata()
    
    def get_shot_chart_data(self, player_id, season, shot_type="All", **kwargs):
        # Check cache first, fallback to API if needed
        
    def get_league_leaders(self, season, stat_category="MIN", **kwargs):
        # Check cache first, fallback to API if needed
        
    def get_player_career_stats(self, player_id, **kwargs):
        # Check cache first, fallback to API if needed
        
    def is_cache_valid(self, cache_key):
        # Check if cache exists and is within max_age_days
        
    def invalidate_cache(self, pattern=None):
        # Remove specific cache files or all cache
```

### 4. Integration Points

**Minimal code changes** by wrapping existing functions:

```python
# In streaky.py
def fetch_shots(pid: int, season: str, shot_type: str = "All", 
                use_cache: bool = True, force_refresh: bool = False):
    if use_cache and not force_refresh:
        cached_data = cache_manager.get_shot_chart_data(pid, season, shot_type)
        if cached_data is not None:
            return cached_data
    
    # Existing API call logic
    # ... then cache the result before returning
    
# In streaky_rankings.py  
def get_players_by_minutes(season, season_type="Regular Season", 
                          use_cache: bool = True, force_refresh: bool = False):
    if use_cache and not force_refresh:
        cached_data = cache_manager.get_league_leaders(season, "MIN")
        if cached_data is not None:
            return cached_data
    
    # Existing API call logic
    # ... then cache the result before returning
```

## Cache Management Features

### 1. Expiration Strategy

- **Default TTL**: 7 days for most data
- **Season-aware expiration**: 
  - Current season data: 1 day TTL
  - Completed seasons: 30 day TTL (near-permanent)
- **Manual invalidation**: Force refresh with `--force-refresh` flag

### 2. Cache Validation

- **Timestamp checking**: Compare file modification time vs TTL
- **Data integrity**: Basic validation of JSON structure
- **Version compatibility**: Cache format versioning for future changes

### 3. Storage Optimization

- **Compression**: Optional gzip compression for large datasets
- **Size limits**: Automatic cleanup of oversized cache directories
- **Selective caching**: Option to cache only specific data types

## Command Line Interface

### New Flags

```bash
# Force fresh API calls, ignore cache
python streaky_rankings.py --force-refresh

# Disable caching entirely
python streaky_rankings.py --no-cache

# Cache management commands
python streaky_rankings.py --cache-info        # Show cache statistics
python streaky_rankings.py --cache-clear       # Clear all cache
python streaky_rankings.py --cache-clear-old   # Clear expired cache only
```

### Backward Compatibility

All existing command combinations continue to work unchanged. Caching is **opt-out** by default.

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create `NBADataCache` class with basic get/set functionality
2. Implement cache key generation and file management
3. Add cache metadata tracking

### Phase 2: Integration
1. Wrap `fetch_shots()` with caching layer
2. Wrap `get_players_by_minutes()` with caching layer  
3. Wrap `get_team_id()` / `PlayerCareerStats` with caching layer

### Phase 3: Management Features
1. Add command line flags for cache control
2. Implement cache expiration and cleanup
3. Add cache statistics and information commands

### Phase 4: Optimization
1. Add compression for large cache files
2. Implement intelligent cache warming
3. Add concurrent cache updates where safe

## Expected Performance Gains

### First Run (Cold Cache)
- **Performance**: Same as current (all API calls required)
- **Benefit**: Data cached for future runs

### Subsequent Runs (Warm Cache)
- **Speed improvement**: 10-50x faster (depending on cache hit rate)
- **API calls**: Reduced by 70-95%
- **Reliability**: Eliminates most network-related failures

### Large-Scale Analysis
- **Current**: 30+ minutes for 50 players across 3 seasons
- **With cache**: 2-5 minutes (after initial cache warming)

## Risk Mitigation

### Data Staleness
- **Solution**: Configurable TTL with season-aware expiration
- **Monitoring**: Cache age displayed in analysis output

### Storage Growth
- **Solution**: Automatic cleanup of old cache files
- **Monitoring**: Cache size limits and warnings

### Cache Corruption
- **Solution**: Graceful fallback to API calls on invalid cache
- **Recovery**: Automatic cache invalidation and refresh

## Configuration Options

```python
# config.py or similar
CACHE_CONFIG = {
    'enabled': True,
    'directory': 'data/cache',
    'max_age_days': 7,
    'max_size_gb': 1.0,
    'compression': False,
    'current_season_ttl_hours': 24,
    'completed_season_ttl_days': 30
}
```

## Success Metrics

1. **Performance**: >10x speed improvement on cached runs
2. **API Usage**: <30% of original API call volume
3. **Reliability**: <5% cache-related failures
4. **Storage**: <1GB cache size for typical usage
5. **User Experience**: Transparent operation with clear cache status

This caching system will significantly improve the user experience while maintaining data freshness and reliability. 
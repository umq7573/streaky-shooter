# NBA Streakiness Analysis

Analyze the streakiness of NBA players' shooting using the run-based streakiness index S.

## Features

- **Run-based Streakiness Index (S)**: A normalized metric that quantifies shooting streakiness independent of field goal percentage
- **Interactive Mode**: Guided setup with beautiful terminal interface
- **Command-line Interface**: Full scriptable automation support
- **Multiple Analysis Types**: Individual players or rankings by minutes played
- **Enhanced Output**: Rich tables and statistics with color coding

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Interactive Mode (Recommended)

**Individual Player Analysis:**
```bash
python streaky.py
```

**Team Rankings Analysis:**
```bash
python streaky_rankings.py
```

### Command Line Interface

**Analyze specific players:**
```bash
python streaky.py --players "Stephen Curry,Klay Thompson" --seasons "2023-24" --shot_type "3PT Field Goal"
```

**Rank top players by minutes:**
```bash
python streaky_rankings.py --seasons "2023-24" --top_n 50 --shot_type "3PT Field Goal"
```

## Streakiness Index S

The run-based streakiness index S measures how clustered makes and misses are:

- **S = 0**: Perfectly streaky (all makes together, all misses together)
- **S = 1**: Perfectly anti-streaky (alternating makes and misses)
- **Range**: [0, 1]
- **FG% Independent**: Compare players with different shooting percentages

See `docs/metric.md` for detailed mathematical explanation.

## Options

### Common Parameters

- `--seasons`: NBA seasons (e.g., "2023-24,2022-23")
- `--shot_type`: Shot types to analyze ("All", "3PT Field Goal", "2PT Field Goal")
- `--metric`: Metric to use ("run" for S index, "momentum" for legacy)
- `--interactive/-i`: Launch interactive mode

### Individual Analysis (`streaky.py`)

- `--players`: Player names (comma-separated)

### Rankings Analysis (`streaky_rankings.py`)

- `--top_n`: Number of top players by minutes (default: 50)
- `--min_shots`: Minimum shots required per player (default: 200)
- `--output`: Save results to CSV file

## Examples

**Find the streakiest 3-point shooters in 2023-24:**
```bash
python streaky_rankings.py --seasons "2023-24" --shot_type "3PT Field Goal" --top_n 100
```

**Compare Stephen Curry's streakiness across seasons:**
```bash
python streaky.py --players "Stephen Curry" --seasons "2023-24,2022-23,2021-22" --shot_type "3PT Field Goal"
```

**Interactive mode for beginners:**
```bash
python streaky_rankings.py
# Follow the guided prompts
```

## Output

Results show:
- **Player rankings** by streakiness
- **Shot statistics** (attempts, makes, FG%)
- **Streakiness scores** with interpretation
- **Summary statistics** for the analysis

Lower S values indicate more streaky shooting patterns. 
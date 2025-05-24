# Run-Based Streakiness Index (S)

## Definition

The run-based streakiness index **S** is a normalized metric that quantifies how streaky a shooting sequence is, independent of the underlying field goal percentage. It is defined as:

```
S = (R - R_min) / (R_max - R_min)
```

Where:
- **R** = actual number of runs in the sequence
- **R_max** = maximum possible number of runs for the given make/miss distribution
- **R_min** = minimum possible number of runs for the given make/miss distribution

## Properties

- **Range**: S ∈ [0, 1]
- **Interpretation**: 
  - S = 0: Perfectly streaky (all makes clustered together, all misses clustered together)
  - S = 1: Perfectly anti-streaky (alternating makes and misses as much as possible)
- **FG% Agnostic**: Two players with different shooting percentages can be directly compared
- **Sample Size Robust**: Valid comparisons across different numbers of shot attempts

## Mathematical Details

### Run Definition
A **run** is a maximal sequence of consecutive identical outcomes. For example:
- Sequence [1,1,0,1,0,0,0] has 5 runs: [1,1], [0], [1], [0,0,0]

### Theoretical Bounds

For k makes out of n total shots:

**Minimum runs (R_min)**:
- If k = 0 or k = n: R_min = 1 (all same outcome)
- Otherwise: R_min = 2 (all makes together, then all misses together)

**Maximum runs (R_max)**:
- If k = 0 or k = n: R_max = 1 (all same outcome)
- If k = n-k (equal makes and misses): R_max = 2k (perfect alternation)
- Otherwise: R_max = 2×min(k, n-k) + 1 (minority outcome fully alternated)

## Worked Examples

### Example 1: Perfectly Streaky
Sequence: [1,1,1,0,0,0] (3 makes, 3 misses)
- R_actual = 2 runs: [1,1,1], [0,0,0]
- R_min = 2 (grouped pattern)
- R_max = 2×3 = 6 (alternating: [1,0,1,0,1,0])
- S = (2 - 2) / (6 - 2) = 0/4 = **0.0** (perfectly streaky)

### Example 2: Perfectly Anti-Streaky  
Sequence: [1,0,1,0,1,0] (3 makes, 3 misses)
- R_actual = 6 runs: [1], [0], [1], [0], [1], [0]
- R_min = 2, R_max = 6
- S = (6 - 2) / (6 - 2) = 4/4 = **1.0** (perfectly anti-streaky)

### Example 3: Uneven Distribution
Sequence: [1,1,0,1,0] (3 makes, 2 misses)
- R_actual = 4 runs: [1,1], [0], [1], [0] 
- R_min = 2 (all makes together: [1,1,1,0,0])
- R_max = 2×min(3,2) + 1 = 2×2 + 1 = 5 (alternating: [1,0,1,0,1])
- S = (4 - 2) / (5 - 2) = 2/3 ≈ **0.67**

### Example 4: Single Outcome Type
Sequence: [1,1,1,1] (4 makes, 0 misses)
- R_actual = 1 run: [1,1,1,1]
- R_min = R_max = 1 (degenerate case)
- S = **0.0** (perfectly streaky by definition)

## Comparison with Legacy Momentum Score

The previous momentum-based metric had several limitations:

1. **FG% Dependent**: Players with different shooting percentages couldn't be directly compared
2. **Unbounded**: No fixed range made interpretation difficult  
3. **Parameter Dependent**: Required tuning of ρ (persistence) and penalty parameters
4. **Complex**: Ad-hoc formula with momentum accumulation and sign-flip penalties

The run-based index S addresses all these issues:

1. **FG% Independent**: Only cares about clustering of makes/misses, not the ratio
2. **Bounded**: Always in [0,1] with clear interpretation
3. **Parameter Free**: No arbitrary constants to tune
4. **Intuitive**: Based on well-understood concept of runs in statistics

## Implementation Notes

The implementation uses vectorized operations with `numpy.diff()` to count runs efficiently:

```python
def _count_runs(flags: np.ndarray) -> int:
    if len(flags) <= 1:
        return 1
    transitions = np.sum(np.diff(flags) != 0)
    return transitions + 1
```

This approach is much faster than iterating through the sequence, especially for large shot datasets. 
---
name: hermes-monte-carlo
description: Method to write, test and display the probabilistic simulations of HERMES (Monte Carlo delivery forecasts from weekly throughput or effort, percentiles, probability of meeting a date, what-if scenarios) in pure, reproducible Python. Use for any forecasting code, its statistical tests, its performance, or any other random computation added to HERMES.
---

# Monte Carlo simulations in HERMES

Spec: the forecasting spec (`docs/spec/forecast.md`, written when the forecasting code is migrated; follow the
`hermes-spec` skill). The current implementation lives in the dotfiles repository, in `hermes/app/gitlab_queries.py`:
`weekly_throughput_samples`, `monte_carlo_forecast` (10,000 trials and a 26-week window by default, in
`hermes/app/config.py`).

## Non-negotiable principles

1. **Pure functions.** The simulation never reads the clock, the database, the network or the settings. It receives
   samples, the remaining work, the trial count, the seed and "today". The caller picks the seed, passes it in, and
   **shows it** next to the result.
2. **Reproducible to the bit.** Use one `random.Random(seed)` instance passed along. Never call the module-level
   `random.*` functions (hidden global state), never `secrets`, and never NumPy's global state. NumPy is not a
   dependency; adding it needs the user's approval.
3. **No per-process randomness.** `hash()` of a `str` changes with `PYTHONHASHSEED`, so never use it to derive a seed
   or an order. Iterating a `set` or a `dict` built from one produces an unstable order: sort before producing output.
   Sum floats in a fixed order (or with `math.fsum`).
4. **Common random numbers.** For a what-if scenario to be comparable with reality, trial `i`, and each item or
   week inside it, gets its own generator **derived from a stable identity** (seed, `i`, item id), never from
   processing order. Derive it with `hashlib.blake2b(f"{seed}:{i}:{item_id}".encode(), digest_size=8)` turned into an
   int, or with SplitMix64. Then reality and scenarios see the same random draws.
5. **One scheduling engine.** A simulation that needs an order replays the existing deterministic planner (queues,
   dependency engine) with drawn values. Never write a second scheduler "for the simulation". With no randomness, the
   simulation must equal the deterministic plan exactly.
6. **Honesty.** Every output carries the trial count, the seed, the data source ("history of n weeks" or "default
   assumption"), and "unreliable" below the minimum sample size. Never give a single date: give P50 · P85 (· P95).
   P85 is the cautious commitment.

## Statistics

- **Throughput model**: sample past weeks with replacement, **zero weeks included** (they are real variability), and
  accumulate them until the remaining work is covered.
- **Percentiles**: nearest rank. The value is the `ceil(p × n)`-th of the sorted results, with the rank clamped to
  [1, n]. Never interpolate between dates.
- **Existing divergence, to settle at migration**: `monte_carlo_forecast` takes `results[int(n × p)]`, one rank above
  nearest rank when `n × p` is an integer. Record the choice in the forecast spec's "Decisions and pitfalls". Don't
  change it silently: displayed forecasts would move.
- **Guards**: an all-zero history is "beyond horizon", not an infinite loop. Bound every trial, for example at
  520 weeks (10 years), and report how many trials hit the bound.
- **Incremental aggregation**: when trials run in chunks, the result must not depend on the chunking.

## Tests to write (pytest, `tests/test_forecast*.py`)

Fixed seed everywhere. No test may depend on luck.

- **Reproducibility**: same input and same seed give equal results (`==` on the whole structure). One chunk and
  twenty chunks give equal results. Run once with `PYTHONHASHSEED=random` to prove no `hash()` leaks.
- **Exact degenerate cases**: a constant throughput of 5 per week with 20 items gives exactly 4 weeks at every
  percentile. With no randomness, the result equals the deterministic plan. Zero remaining work gives 0.
- **Convergence** against a known law: for a single draw from a known distribution with 20,000 trials, P50 and P85
  land within a tolerance of the analytic values. **Justify the tolerance in a comment**, with the standard error of
  the empirical quantile, √(p(1−p)/n) / f(xₚ), times 4.
- **Properties with common random numbers**: more remaining work never brings an end date earlier, a lower
  throughput never brings it earlier, and a scenario that changes nothing gives the same result as reality.
- **Poor data**: an empty history gives the default law and "unreliable". All-zero throughput gives "beyond horizon"
  within the bound, with no hang.
- **Docstring**: each test starts with the requirement it proves (`"""forecast R3: …"""`).

## Performance and execution

- Budget: write one in the spec, for example 10,000 trials × 500 items < 1 s on CPython. **Measure before
  optimising**, in a test marked `@pytest.mark.slow` that is kept out of the default run if it is slow.
- Hot loop: bind locals (`rng_random = rng.random`), draw in batches (`rng.choices(samples, k=…)`), and avoid creating
  one object per item per trial. Precompute orders, capacities and the dependency graph **once**.
- Web: a simulation is CPU-bound and must never block the event loop. Run it in a worker thread (a sync route, or
  `run_in_threadpool`). Cache it by a fingerprint of its inputs, and recompute only when the data changes.

## Display

- Use the HERMES design charter (the `hermes-design` skill, still in dotfiles until migrated): figures in IBM Plex
  Mono with tabular digits. Colour states something, never decorates.
- Histogram with the value written on each bar, and percentiles as labelled lines. Provide a full text description
  for screen readers.
- Show probabilities as whole percentages. "At risk" is shown with an outline and an icon, never by hue alone.
- When the fingerprint of the data changes, mark the result "stale" (text and icon).

## Trace

Every numeric decision goes into "Decisions and pitfalls" of the forecast spec, with its justification: bound, law,
minimum sample, tolerance, chunk size, window.

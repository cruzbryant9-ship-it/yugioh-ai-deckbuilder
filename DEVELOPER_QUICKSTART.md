# Developer Quickstart

## Main Program

```powershell
python yugioh_ai_deckbuilder.py
```

If Windows does not have `python` on PATH in this workspace, use the bundled runtime:

```powershell
& 'C:\Users\theeg\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' yugioh_ai_deckbuilder.py
```

## Training

```powershell
python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 2
```

With matchup context:

```powershell
python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 2 --matchup combo --going second
```

## Evaluation

```powershell
python evaluate_learning.py --archetype "Blue-Eyes" --mode meta --runs 2
```

## Opponent Analysis

```powershell
python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second
```

This parses the opponent decklist, merges inferred and curated profile knowledge, recommends side plans, and reports graph/resource/probability metrics.

## Matchup Matrix

Smoke matrix:

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```

Full matrix:

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 5 --use-curated-opponents --full
```

## Validators

Quick stabilization check:

```powershell
python validate_stabilization_a.py
```

Latest Phase 5 feature check:

```powershell
python validate_phase5x.py
```

Matrix validator smoke/full:

```powershell
python validate_phase5m.py --smoke
python validate_phase5m.py --full
```

## Runtime Profiling

```powershell
python profile_runtime.py --smoke
```

The profiler prints command durations, success/failure, slowest scripts, and practical optimization targets.

## Recommended Workflow

1. Make a small change.
2. Run `python -m py_compile` on touched files.
3. Run the nearest validator.
4. Run `python validate_stabilization_a.py` before larger handoff points.
5. Use full matrix validation only before major milestones because it is intentionally slower.

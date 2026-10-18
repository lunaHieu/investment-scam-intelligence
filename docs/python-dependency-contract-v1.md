# Python Dependency Contract V1

The acquisition, verification, registry, and review-control paths use only the
Python standard library. They can therefore run in Python 3.10 or 3.11 without
the modeling stack. The project venv that produced the current artifacts uses
Python 3.10; CI checks both supported minor versions.

Two explicit optional environments are declared in `pyproject.toml`:

- `baseline`: NumPy, SciPy, scikit-learn, and joblib for the frozen classical
  text and metadata experiments.
- `embedding`: NumPy, scikit-learn, Tokenizers, PyTorch, and Transformers for
  the offline embedding challenger workflow.

Direct versions are pinned in `pyproject.toml`. The complete transitive
environment used for the frozen embedding experiment remains pinned in
`configs/text_semantic_challenger_v4_requirements.lock.txt`.

Install only the environment required by the task:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[baseline]"
```

or, for the already authorized offline embedding workflow:

```powershell
.venv\Scripts\python.exe -m pip install -r configs\text_semantic_challenger_v4_requirements.lock.txt
```

Adding a new third-party import under `scripts/` or `src/` requires updating
the declared dependency groups, the frozen lock when applicable, and the
dependency-contract test. Dependency changes do not open model, validation,
test, training, scoring, or deployment gates.

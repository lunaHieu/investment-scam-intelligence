# Parser-Bound Supplemental Live Gate V1

The live adapter is implemented but fail-closed. A generic instruction to
continue does not authorize supplemental network execution. The gate requires
a separate exact PBC05-PBC08 owner amendment and independent QA, both tracked
in Git, a clean working tree, `HEAD == origin/main`, verified release inputs and
absent final/partial outputs.

The capability token is process-local and cannot be forged by callers. The
real opener is constructed only after preflight returns true. Until the owner
explicitly authorizes supplemental network execution, `--verify-only` is the
only permitted path and performs zero network operations.

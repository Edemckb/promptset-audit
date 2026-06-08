# Contributing

Contributions are welcome, especially new validation rules backed by small JSONL fixtures.

1. Keep runtime dependencies at zero where possible.
2. Add tests for every behavior change.
3. Run `python -m unittest discover -s tests -v`.
4. Explain how the proposed rule prevents a concrete dataset problem.

Please do not add rules that inspect or transmit prompt contents over the network.


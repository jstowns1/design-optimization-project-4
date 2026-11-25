# Verification benchmarks

## V1 — Cantilever tube with a downward tip load

Purpose: Check whether our frame solver predicts the tip displacement
of a single tube clamped at one end.

### Inputs
- Length, L = 1.00 m
- Downward tip load, P = 20 N
- Young's modulus, E = 200 × 10^9 Pa
- Outside diameter, Do = 0.020 m
- Inside diameter, Di = 0.016 m
- Left end fixed. Load applied at the right end. Self-weight omitted.

### Team hand calculation
1. Tube second moment of area:
   I = (π/64) × (Do^4 − Di^4) = 0.00000000464 m^4

2. Downward tip deflection:
   δ = P × L^3 / (3 × E × I) = 0.007189 m

3. Convert to millimeters:
   δ × 1000 = 7.18857 mm downward

### Solver comparison — fill in after running the code
- Solver tip deflection magnitude: 7.18857015 mm
- Percent error: |solver − hand calculation| / hand calculation × 100 = 0.00000207 %

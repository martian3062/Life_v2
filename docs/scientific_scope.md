# Scientific scope: headless F0 prototype

The blueprint defines the longer project. This implementation deliberately starts at its F0
software-verification level. All enabled model parameters have hypothetical evidence.

## Operational target

`implemented_aggregate_maintenance_rule_present` is true for `maintenance_fast` and
`maintenance_buffered`; it is false for `mineral_growth` and `abiotic_catalyst`.
This label identifies an implemented effective kinetic rule. It makes no biological claim.
The broader blueprint target, `implemented_protocell_mechanism_present`, is deferred until
individual maintenance, finite internal inventories and division are implemented and verified.

## Effective transformations

Resource R becomes structure B, then B becomes waste W. Each pool contains one conserved token
per unit, so R + B + W is invariant in a closed compartment. These are not chemical species.
There is no atomic formula, charge, chemical potential, free-energy or enthalpy interpretation.

At reference temperature 298.15 K:

- Growth transfers a fraction `1 - exp(-growth_s * rate_scale * catalyst * dt)` of R to B.
- Loss transfers a fraction `1 - exp(-loss_s * rate_scale * dt)` of the updated B to W.
- For maintenance fixtures, `catalyst = concentration_B / (concentration_B + 0.5 token/m3)`.
- For abiotic controls, `catalyst = 1`.
- Both rates are multiplied by `exp(thermal_coefficient_K * (T - 298.15))`.

The registry is `xeno/data/f0_registry.json`. A shared rate multiplier is drawn uniformly from
[0.85, 1.15] for each world, independently of the appearance stream. The chosen coefficients,
the saturation scale 0.5 token/m3 and all condition limits are engineering assumptions.

Growth and loss are integrated as ordered bounded transfers. No negative concentrations are
clipped. An invalid state rejects the whole action. Floating-point correction is zero.
The independent reversible A↔B fixture uses SciPy BDF and an analytic reference solution;
this validates that fixture, not the biological interpretation of the token models.

## World geometry and timing

Default geometry is an 8×8 layer of compartments, width 0.01 m and nominal thickness 0.01 m.
Initial volume per compartment is 1e-6 m3. All compartments in an episode use the same family.
Four disclosed sites map to corners. Deterministic movement is an abstract point rover at
0.01 m/s with no terrain obstacles or collision physics.

Transport uses a no-flux finite-volume network with face conductance `D * dx`, where
`D = 1e-7 m2/s`. Sampling reduces accessible fluid volume while retaining face geometry.
Empty compartments have sealed faces. Backward Euler solves the conservative transport system;
then bounded reaction transfers execute at each solver step (default ≤0.25 s). This is a
first-order operator split. Convergence tests cover the analytic fixture, local reaction
stepping and transport resolution. Comprehensive convergence of every intervention decision
under spatial and temporal refinement remains a research gate.

Scientific time advances only at committed action boundaries. Camera/render timing is absent.
The only supported condition profile is nominal aqueous operation at 101325 Pa. World setup
accepts 285–305 K so a +10 K lab intervention stays within the 285–315 K model domain.
These are software validity limits, not validation of aqueous chemistry.

## Samples and instruments

Collection removes a proportional inventory and volume from the source. A split consumes the
original and produces equal siblings. Used chambers retain material and occupy containers;
they cannot be reused as fresh matched controls. Samples are ideally preserved until an
experiment; this intentionally pauses their chemistry. World compartments continue to evolve.
Collection/handling time belongs to the mission clock, not chamber reaction time.

A resource pulse adds 2 token/m3 of R to the treatment, with negligible reagent volume.
Its total amount is recorded in the external input ledger. A temperature experiment applies
+10 K to the treatment only. Both chambers evolve over the same interval, using the same model.
Nine time points produce 18 instrument readings per paired experiment.

Sensors independently add Gaussian noise with standard deviation 0.04 token/m3. Values below
0.08 token/m3 are censored with `value: null`; they are not exact zeros. Repeated observation
GET requests return the same committed result and do not produce additional noise draws.
There are no camera, Raman or mass-spectrometry observations in this build.

## Investigation and evaluation limits

The adaptive baseline changes its next intervention based on score uncertainty. It is not the
blueprint's expected-information-gain policy. Scores use qualitative early-response heuristics;
they have no calibration claim. Weak responses and prior mismatch cause abstention.
Reports cite committed observation IDs; this checks traceability, not truth of free-text claims.

The development comparison runs all policies on the same family/seed combinations with the
same budget caps. Actual resource expenditure is reported. Passive runs may spend less than
intervention runs. Budget-matched passive measurement studies, held-out families, validation
threshold selection, confidence intervals and trained/calibrated inference remain pending.
Summary TPR/FPR use every valid episode at a fixed score threshold of 0.5, including abstentions;
coverage is reported separately. These are diagnostic development numbers.

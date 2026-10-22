# Model registries

The runtime's canonical fixture registry is `xeno/data/f0_registry.json`; packaging includes it.
Every enabled species and effective reaction has `hypothetical` evidence. All three species use
a conserved abstract token basis. The rate parameters, condition limits and generation ranges
are engineering assumptions. Their values support software verification, not chemical claims.

Physical reaction records, measured kinetics and silicon-containing species remain deferred.
The blueprint's silica net equation remains disabled: it has no validated kinetic model here.
Changes to the registry require a model-version change and new benchmark runs.

# Detection packs

Mayajal can assemble common, machine-specific, and structured detection metadata into a content-addressed bundle for each lab session. Existing machine manifests do not need to change: the initial resolver infers profiles from existing machine names, images, descriptions, operating systems, and ports.

## Rollout modes

Set `MAYAJAL_DETECTION_ENGINE_MODE` before starting the API:

- `legacy` (default): load machine rules and use the existing report classifier. This is the immediate rollback mode.
- `shadow`: load resolved detection packs and immutable bundles, but retain legacy report classification.
- `packs`: load resolved packs and classify network alerts by registered Suricata SID. Unregistered telemetry remains `Unmapped` instead of being guessed from protocol names.

## Pack layout

Each platform-owned pack is stored under `assets/detection-packs/<pack-id>/` and contains a `manifest.json` plus zero or more `.rules` files. The manifest maps every platform SID to stable Mayajal and ATT&CK metadata.

The current automatic policy always selects `baseline`, then adds `reconnaissance`, `web`, and `credential-attacks` when existing machine data indicates they are relevant. The resolver returns a reason for every selection.

## Runtime and rollback

Resolved bundles are stored by SHA-256 digest under `api_test/runtime/detection-bundles/`. A session records its bundle digest, and its generated Suricata directory records both `detection-bundle.json` and `detection-registry.json`.

To roll back detection behaviour, set:

```text
MAYAJAL_DETECTION_ENGINE_MODE=legacy
```

Previously generated bundles are intentionally retained so historical sessions remain reproducible. Do not edit a published pack version in place; increment its version when changing its rules or metadata.

## Validation

The bundle builder rejects missing or unsafe rule paths, pack rules without metadata, and SID collisions between platform packs and machine-specific rules. Run the regression suite with:

```text
api_test/.venv/bin/python -m pytest api_test/tests/test_detection_packs.py api_test/tests/test_core.py -q
```

Production publishing should additionally run `suricata -T` using the deployed Suricata image before enabling `packs` as the default.

# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project purpose
- Automates multi-station checkout of Aerotech stages. The GUI (Tkinter + PyQt5) allocates stations, fetches job info, configures stage specs, connects to Automation1 controllers, generates/loads MCDs, runs validation (halls, homing, limits), performs burn-in, logs results, and updates external systems.

Common commands (pwsh on Windows)
- Run the checkout GUI
```pwsh path=null start=null
python UI.py
```

- Run the Secondary station monitor UI only (fullscreen dashboard)
```pwsh path=null start=null
python secondary_UI.py
```

- Verify Aerotech Automation1 installation is discoverable by the MCD pipeline
```pwsh path=null start=null
Test-Path 'C:\Program Files (x86)\Aerotech\Controller Version Selector\Bin\Automation1'
```

- List available drive templates (e.g., iXA4, XC4e) that GenerateMCD v2 can use
```pwsh path=null start=null
python -c "from GenerateMCD_v2 import AerotechController; m=AerotechController.without_file_saving(); m.initialize(); print(m.get_available_drives())"
```

- Debug-populate a template without talking to hardware (writes a DEBUG_populated_template_*.json)
```pwsh path=null start=null
python - << 'PY'
from GenerateMCD_v2 import AerotechController
m = AerotechController.without_file_saving()
m.initialize()
# Minimal example: supply mechanical + electrical separated configs
specs = {"Travel": "-025", "Feedback": "-E1"}
elec  = {"Bus Voltage": "80", "Motor Supply Voltage": "-AC", "Current Axes 1 and 2": "-20"}
print(m.debug_template_population(specs_dict=specs, electrical_dict=elec, stage_type="ANT95L", axis="ST01", drive_type="iXA4"))
PY
```

- Generate an MCD to a specific directory (without running the full GUI)
```pwsh path=null start=null
python - << 'PY'
from GenerateMCD_v2 import AerotechController
m = AerotechController.for_specific_output_dir(output_dir=r"C:\Temp\mcd_out")
m.initialize()
specs = {"Travel": "-025", "Feedback": "-E1"}
elec  = {"Bus Voltage": "80", "Motor Supply Voltage": "-AC", "Current Axes 1 and 2": "-20"}
calculated_mcd, warnings, path = m.calculate_parameters(
    specs_dict=specs, electrical_dict=elec, stage_type="ANT95L", axis="ST01", drive_type="iXA4"
)
print("Saved:", path)
if warnings: print("Warnings:", warnings)
PY
```

Notes on build, lint, and tests
- Build: No packaging/build step is defined; this repo runs as scripts/modules.
- Lint/format: No linter/formatter config is present in-repo.
- Tests: There is no unit test suite configured. Validation is exercised via the GUI flows (allocation, halls check, homing, limits, burn-in). To run “a single test”, use the GUI with a reduced number of stations and proceed through a single axis flow.

Environment and external dependencies
- Hardware/SDK
  - Requires Aerotech Automation1 installed (v2.11+; the code auto-detects the latest version from Controller Version Selector paths).
  - Controllers are addressed by IP from station_config.json (auto-created if missing). Default station map: ST01..ST05 → 192.168.1.10..14.
- Python libs commonly imported by the flows include PyQt5, tkinter, numpy, matplotlib, requests, pythonnet (clr), and Google Cloud BigQuery client. Install per your environment as needed before running.
- BigQuery: The GUI queries job data using query.txt. Ensure Application Default Credentials are set up for your Google Cloud environment before using that feature.
- Shared utilities: Several modules are imported from a shared network path (K:\10. Released Software\Shared Python Programs\production-2.1), e.g., Logger, DecodeFaults, sheets_update. Ensure that path is reachable for the environment where you run the GUI.

High-level architecture and flow
- UI tier (operator workflow)
  - UI.py (Tkinter primary UI)
    - Collects job number, operator, comments, number of stations, voltage, etc.
    - “Configure” uses BigQuery (query.txt) to fetch PartNum/PartDescription, extracts a stage “smart string”, and launches the PyQt5 BallscrewSizer to produce:
      - specs_dict (mechanical options)
      - param_dict (derived parameters like travel, nominal values)
    - Integrates the SecondaryUI dashboard (secondary_UI.py) in a background thread for 10-station log/status display with per-station Abort.
    - Allocates stations via StationManager and connects to Automation1 controllers by station IPs.
    - Invokes the checkout pipeline (checkout_test.stage_checkout.test) with per-run context (speed, duty cycle, absolute/incremental, bus voltage, etc.).

- Station orchestration
  - station_manager.py manages station availability, persistence (station_config.json), and a background thread to refresh status and process updates.
  - station_manager_instance.py exposes a process-wide getter/setter so other modules (e.g., checkout_test) can release stations on abort.

- Checkout pipeline (core logic)
  - checkout_test.py coordinates multi-axis testing. Major stages:
    - MCD generation/loading per axis using GenerateMCD_v2.AerotechController (drive-specific templates and separated mechanical/electrical configs). The code also injects AxisName into the MCD Parameters XML before upload.
    - Enable and fault handling. Parallel threads per axis with robust abort logic; uses SecondaryUI to surface status and provides per-station Abort.
    - Halls check: prefers MSET sequence; if travel-limited or faulted, switches to a fallback method that collects hall/encoder data and validates sequence/direction.
    - Homing, hardstop checks, software limits, burn-in execution (with BurnIn.py).
    - Logging to files (e.g., logs with hall states.txt, ST02_hall_states.txt, ST03_hall_states.txt) and updates to Google Sheets (sheets_update.Checkout_Sheet).

- Burn-in
  - BurnIn.py orchestrates move-to-start, speed ramp, timed burn-in cycles, and plotting (BurnInPlotting). It mirrors the SecondaryUI logging and abort handlers per station.

- MCD generation subsystem
  - GenerateMCD_v2.py provides a refactored architecture around Aerotech .NET DLLs:
    - McdProcessor: Handles pythonnet/clr loading, discovers Automation1 DLLs, converts JSON↔MCD, calculates parameters, and extracts servo/feedforward parameters from MCD XML.
    - FileManager with NamingStrategy and OutputStrategy variants (default, smart-string, specific directories).
    - AerotechController: Facade with factory methods such as:
      - with_default_config(), with_file_saving(...), with_smart_string_naming(...), without_file_saving(), for_specific_output_dir(...), for_checkout_workflow(...)
    - Strict config separation: specs_dict (mechanical) vs. electrical_dict (drive). See GenerateMCD_v2_Instructions.md for detailed usage patterns and examples.
  - Templates and config
    - GenerateMCD_Assets/ contains drive templates (e.g., iXA4_Template.json, XC4e_Template.json) and a drive_config.json used to validate allowable electrical options and defaults.

Repository-specific conventions
- When working with GenerateMCD_v2, avoid using the name "controller" for the MCD processor—reserve “controller” for actual Automation1 controller objects used to move axes. Prefer mcd_processor/mcd_handler.
- Calculated MCDs for checkout runs are typically saved to O:\CMP Check-out\Parameter Files\Automation1 when using for_checkout_workflow; adjust as needed if this path is not available.

Troubleshooting tips tied to this codebase
- If MCD initialization fails with version errors, confirm Automation1 2.11+ is installed and discoverable (see command above). Restart the shell if you just installed it.
- If BigQuery lookups fail, the GUI will continue but won’t auto-populate the smart string; ensure ADC is configured.
- If shared utilities are missing (Logger, DecodeFaults, sheets_update), verify the K:\ path exists and is accessible from this machine.

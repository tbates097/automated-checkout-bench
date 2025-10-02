# GenerateMCD v2.0 Usage Instructions

## Overview

GenerateMCD v2.0 provides a flexible, reusable architecture for working with Aerotech MCD files with **clean separation of mechanical and electrical configurations**. It uses drive-specific templates, comprehensive validation, and a strategy pattern design for maximum flexibility and maintainability.

## 🚀 Key Features

- **Drive-Specific Templates**: Auto-discovers and uses appropriate templates (iXA4, XC4e, XR3, etc.)
- **Comprehensive Validation**: Validates configurations before processing
- **Template Discovery**: Auto-scans available drive types and provides drive information
- **Backward Compatibility**: Existing code continues to work

## Architecture Components

- **McdProcessor**: Handles core .NET DLL operations and drive-specific template loading
- **FileManager**: Manages file operations, naming, and paths
- **AerotechController**: Main facade that orchestrates everything
- **Strategy Classes**: Different approaches for naming and output handling

## Four Main Use Cases

GenerateMCD supports four primary operations with **separated mechanical/electrical configurations**:

1. **Convert template JSON to MCD object** (optionally save) - uses `json_to_mcd()`
2. **Convert MCD file to JSON** (always saves) - uses `mcd_to_json()`
3. **Generate MCD with calculated parameters** from separated specifications - uses `calculate_parameters()`
4. **Recalculate existing MCD and extract parameters** - uses `recalculate_and_extract()`

## Configuration Separation - IMPORTANT!

### ✅ **Clean Configuration Structure**
```python
# Mechanical configurations ONLY (stage-specific)
specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1", 
    "Cable Management": "-CMS2"
}

# Electrical configurations ONLY (drive-specific)
electrical_dict = {
    "Bus Voltage": "80",
    "Motor Supply Voltage": "-AC",
    "Current Axes 1 and 2": "-20"
}
```

### ❌ **Old Mixed Structure (Deprecated)**
```python
# DON'T DO THIS - mixing mechanical and electrical options
specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1",
    "Bus Voltage": "80"  # ← Electrical option mixed in
}
```

## Drive-Specific Templates

GenerateMCD v2.0 automatically scans for drive-specific templates:

### Available Drive Types
- **iXA4**: Multi-axis discrete drive (`iXA4_Template.json`)
- **XC4e**: Single-axis drive (`XC4e_Template.json`)
- **XR3**: Multi-axis rack (`XR3_Template.json`)  
- **MS**: Generic template (`MS_Template.json`)
- **And more...** (automatically discovered)

### Template Discovery
```python
# Get available drive templates
available_drives = mcd_processor.get_available_drives()
print(f"Available: {available_drives}")  # ['iXA4', 'XC4e', 'XR3', 'MS', ...]

# Get drive information
drive_info = mcd_processor.get_drive_info("iXA4")
print(f"Multi-axis: {drive_info['is_multi_axis']}")
print(f"Template exists: {drive_info['template_exists']}")
```

## Quick Start Guide

### Important: Variable Naming Convention

⚠️ **NEVER use `controller` as a variable name** - this is typically used for actual Automation1 controller objects.

✅ **Use these instead:** `mcd_processor`, `mcd_handler`, `mcd_generator`

### Basic Usage Pattern

```python
sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
from GenerateMCD_v2 import AerotechController

# 1. Create the processor
mcd_processor = AerotechController.with_default_config()

# 2. Initialize
mcd_processor.initialize()

# 3. Use separated configurations
specs_dict = {"Travel": "-025", "Feedback": "-E1"}
electrical_dict = {"Bus Voltage": "80", "Current": "-20A"}

# 4. Generate MCD with drive-specific template
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
    specs_dict=specs_dict,
    electrical_dict=electrical_dict,
    stage_type="ANT95L",
    axis="ST01", 
    drive_type="iXA4"
)
```

## Factory Methods - Choose Your Configuration

### 1. `with_default_config()`
**Use when:** You want standard behavior with minimal configuration

```python
mcd_processor = AerotechController.with_default_config()
```

**Behavior:**
- Saves files to current working directory
- Uses standard naming (`Calculated_`, `Uncalculated_`, etc.)
- Overwrites existing files
- Saves all file types

### 2. `with_file_saving(output_dir, ...)`
**Use when:** You want to control where files are saved

```python
mcd_processor = AerotechController.with_file_saving(
    output_dir=r"C:\MyMCDs",
    separate_dirs=True,  # Creates "calculated" and "uncalculated" subdirs
    overwrite=False      # Creates versioned files instead
)
```

### 3. `with_smart_string_naming(smart_string, ...)`
**Use when:** You want files named using a smart string (like from barcode scans)

```python
mcd_processor = AerotechController.with_smart_string_naming(
    smart_string="ANT95L-025-E1-UF",
    output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
)
```

**Results in filename:** `ANT95L-025-E1-UF.mcd`

### 4. `without_file_saving()`
**Use when:** You only want to work with objects in memory

```python
mcd_processor = AerotechController.without_file_saving()
```

### 5. `for_checkout_workflow(smart_string, output_dir)`
**Use when:** You need the full checkout automation setup

```python
mcd_processor = AerotechController.for_checkout_workflow(
    smart_string="ANT95L-025-E1-UF",
    output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
)
```

## Core Methods - The Four Main Operations

### Operation 1: Convert JSON Template to MCD

```python
mcd_processor = AerotechController.with_file_saving(output_dir=r"C:\Output")
mcd_processor.initialize()

# Separated configurations
specs_dict = {"Travel": "-025", "Feedback": "-E1"}
electrical_dict = {"Bus Voltage": "80", "Current": "-20A"}

mcd_obj, warnings, file_path = mcd_processor.json_to_mcd(
    specs_dict=specs_dict,
    electrical_dict=electrical_dict,
    stage_type="ANT95L", 
    axis="ST01",
    drive_type="iXA4",  # Uses iXA4_Template.json
    save_file=True
)
```

### Operation 2: Convert MCD to JSON

```python
mcd_processor = AerotechController.with_default_config()
mcd_processor.initialize()

warnings = mcd_processor.mcd_to_json(
    mcd_path="input.mcd",
    output_json_path="output.json"
)
```

### Operation 3: Generate Calculated MCD from Separated Specifications

```python
mcd_processor = AerotechController.for_checkout_workflow(
    smart_string="ANT95L-025-E1-UF",
    output_dir=r"O:\MyMCDs"
)
mcd_processor.initialize()

# Clean separation of configurations
specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1", 
    "Cable Management": "-CMS2"
}

electrical_dict = {
    "Bus Voltage": "80",
    "Motor Supply Voltage": "-AC",
    "Current Axes 1 and 2": "-20"
}

calculated_mcd, warnings, file_path = mcd_processor.calculate_parameters(
    specs_dict=specs_dict,
    electrical_dict=electrical_dict,
    stage_type="ANT95L",
    axis="ST01",
    drive_type="iXA4",
    save_calculated=True,
    save_uncalculated=False
)
```

### Operation 4: Recalculate Existing MCD and Extract Parameters

```python
mcd_processor = AerotechController.without_file_saving()
mcd_processor.initialize()

servo_params, ff_params, mcd_obj, _, warnings = mcd_processor.recalculate_and_extract(
    mcd_path="existing.mcd"
)

# servo_params and ff_params are dictionaries with extracted parameters
print(f"Servo parameters: {servo_params}")
print(f"Feedforward parameters: {ff_params}")
```

## Configuration Validation

Validate your separated configurations before processing:

```python
# Validate separated configurations
validation = mcd_processor.validate_configuration_setup(
    specs_dict=specs_dict,
    electrical_dict=electrical_dict, 
    drive_type="iXA4"
)

if not validation['valid']:
    print("❌ Configuration errors:")
    print(f"  Mechanical: {validation['mechanical_validation']['errors']}")
    print(f"  Electrical: {validation['electrical_validation']['errors']}")
    print(f"  General: {validation['errors']}")
else:
    print("✅ Configuration validated successfully!")
    
# Show drive information
print(f"Drive info: {validation['drive_info']}")
```

## Real-World Examples

### Example 1: Checkout Automation Workflow (Updated)

```python
def setup_checkout_mcd_processor(smart_string, bus_voltage):
    """Set up MCD processor for checkout automation with separated configs"""
    
    mcd_processor = AerotechController.for_checkout_workflow(
        smart_string=smart_string,
        output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
    )
    
    # Don't save uncalculated files for checkout
    mcd_processor.configure_saving(uncalculated=False)
    
    return mcd_processor

# Usage in checkout_test.py with separated configurations
smart_string = "ANT95L-025-E1-UF"  # From barcode scan
bus_voltage = "80"  # From UI selection

mcd_processor = setup_checkout_mcd_processor(smart_string, bus_voltage)
mcd_processor.initialize()

for axis in test_axes:
    # Clean separation of mechanical and electrical configs
    specs_dict = {
        "Travel": "-025",
        "Feedback": "-E1", 
        "Cable Management": "-CMS2"
    }
    
    electrical_dict = {
        "Bus Voltage": bus_voltage,        # User-selected from UI
        "Motor Supply Voltage": "-AC",     # Hardcoded for iXA4
        "Current Axes 1 and 2": "-20"     # Hardcoded for iXA4
    }
    
    calculated_mcd, warnings, mcd_path = mcd_processor.calculate_parameters(
        specs_dict=specs_dict,
        electrical_dict=electrical_dict,
        stage_type=stage_type,
        axis=axis,
        drive_type="iXA4"  # Uses iXA4_Template.json
    )
    print(f"Created MCD: {mcd_path}")
    # File: "O:\CMP Check-out\Parameter Files\Automation1\ANT95L-025-E1-UF.mcd"
```

### Example 2: Multiple Drive Types

```python
def generate_mcds_for_different_drives():
    """Generate MCDs for different drive types with appropriate electrical configs"""
    
    mcd_processor = AerotechController.with_file_saving(output_dir=r"C:\MultiDrive")
    mcd_processor.initialize()
    
    # Same mechanical specs for all
    specs_dict = {
        "Travel": "-100",
        "Feedback": "-E1"
    }
    
    # Different electrical configs per drive
    drive_configs = {
        "iXA4": {
            "Bus Voltage": "80",
            "Motor Supply Voltage": "-AC",
            "Current Axes 1 and 2": "-20"
        },
        "XC4e": {
            "Bus Voltage": "120", 
            "Current": "-40A",
            "Multiplier": "-MX1"
        },
        "XR3": {
            "Bus Voltage": "160",
            "Current Axes 1 and 2": "-30"
        }
    }
    
    for drive_type, electrical_dict in drive_configs.items():
        print(f"\nGenerating MCD for {drive_type}:")
        print(f"  Electrical config: {electrical_dict}")
        
        calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
            specs_dict=specs_dict,
            electrical_dict=electrical_dict,
            stage_type="PRO165LM",
            axis="ST01",
            drive_type=drive_type
        )
        
        print(f"  ✅ Created: {path}")
```

### Example 3: Parameter Extraction with Validation

```python
def extract_parameters_with_validation(mcd_path):
    """Extract servo parameters with comprehensive error checking"""
    
    mcd_processor = AerotechController.without_file_saving()
    mcd_processor.initialize()
    
    print(f"Available drive templates: {mcd_processor.get_available_drives()}")
    
    try:
        servo_params, ff_params, _, _, warnings = mcd_processor.recalculate_and_extract(mcd_path)
        
        if warnings:
            print(f"⚠️ Warnings: {warnings}")
            
        # Display organized results
        print(f"\n✅ Extracted {len(servo_params)} servo parameters and {len(ff_params)} feedforward parameters")
        
        for axis, params in servo_params.items():
            print(f"\nAxis {axis} servo parameters:")
            for param in params[:3]:  # Show first 3
                print(f"  {param['name']}: {param['value']}")
            if len(params) > 3:
                print(f"  ... and {len(params) - 3} more")
        
        return servo_params, ff_params
        
    except Exception as e:
        print(f"❌ Error extracting parameters: {e}")
        return None, None
```

## Drive-Specific Electrical Configuration Examples

### iXA4 (Multi-Axis Servo Drive)
```python
electrical_dict = {
    "Bus Voltage": "80",
    "Motor Supply Voltage": "-AC",      # or "-DC"
    "Current Axes 1 and 2": "-20",
    "Current Axes 3 and 4": "-10",
    "Expansion Board": "-EB1",
    "Multiplier Axes 1 and 2": "-MX2",
    "Multiplier Axes 3 and 4": "-MX1"
}
```

### XC4e (Single-Axis Drive)
```python
electrical_dict = {
    "Bus Voltage": "120", 
    "Current": "-40A",
    "Expansion Board": "-EB0",
    "Multiplier": "-MX1"
}
```

### XR3 (Multi-Axis Rack)
```python
electrical_dict = {
    "Bus Voltage": "160",
    "Current Axes 1 and 2": "-30",
    "Expansion Board": "-EB2"
}
```

## Error Handling & Validation

```python
try:
    mcd_processor = AerotechController.for_checkout_workflow(
        smart_string="ANT95L-025-E1-UF",
        output_dir=r"C:\Output"
    )
    mcd_processor.initialize()
    
    # Validate before processing
    validation = mcd_processor.validate_configuration_setup(
        specs_dict=specs_dict,
        electrical_dict=electrical_dict,
        drive_type="iXA4"
    )
    
    if not validation['valid']:
        print(f"❌ Validation failed: {validation['errors']}")
        return
    
    calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
        specs_dict=specs_dict,
        electrical_dict=electrical_dict,
        stage_type="ANT95L",
        axis="ST01",
        drive_type="iXA4"
    )
    
    if warnings:
        print(f"⚠️ Warnings: {warnings}")
        
    print(f"✅ Successfully created MCD: {path}")
    
except FileNotFoundError as e:
    print(f"❌ Template not found: {e}")
    available = mcd_processor.get_available_drives() 
    print(f"Available drive types: {available}")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
```

## Backward Compatibility

GenerateMCD v2.0 maintains full backward compatibility. Old code will continue to work:

```python
# Old style (still works but uses mixed configurations)
mcd_processor = AerotechController()
mcd_processor.initialize()

# Legacy method automatically separates mixed specs
old_specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1",
    "Bus Voltage": "80"  # Will be extracted to electrical_dict
}

calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
    old_specs_dict, "ANT95L", "ST01"
)

# Legacy methods still available
mcd_obj, path, warnings = mcd_processor.convert_to_mcd(old_specs_dict, "ANT95L", "ST01")
```

## Best Practices

1. **Always separate mechanical and electrical configurations** - don't mix them
2. **Use drive-specific templates** - specify `drive_type` for best results
3. **Validate configurations before processing** - use `validate_configuration_setup()`
4. **Always call `initialize()` before using the processor**
5. **Use descriptive variable names** (`mcd_processor`, not `controller`)
6. **Handle warnings and errors appropriately**
7. **Choose the right factory method** for your use case
8. **Discover available drive types** with `get_available_drives()`

## Migration from v1.0

### Configuration Changes
```python
# OLD v1.0 style (mixed configurations)
specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1", 
    "Bus Voltage": "80"  # ❌ Mixed electrical option
}

# NEW v2.0 style (clean separation)
specs_dict = {
    "Travel": "-025",
    "Feedback": "-E1"
}

electrical_dict = {
    "Bus Voltage": "80"  # ✅ Proper separation
}
```

### Method Updates
```python
# OLD method call
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
    specs_dict, stage_type, axis
)

# NEW method call (more specific)
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
    specs_dict=specs_dict,
    electrical_dict=electrical_dict,
    stage_type=stage_type,
    axis=axis,
    drive_type="iXA4"  # ✅ Drive-specific template
)
```

## Troubleshooting

### Common Issues

1. **"Template not found for drive_type"**
   - Solution: Check available drives with `get_available_drives()`
   - Ensure template file exists: `{drive_type}_Template.json`

2. **"Electrical option found in specs_dict"**
   - Solution: Move electrical options to `electrical_dict`
   - Keep only mechanical stage options in `specs_dict`

3. **"Configuration validation failed"**
   - Solution: Use `validate_configuration_setup()` to see specific errors
   - Check that electrical options match your drive template

4. **"Controller has not been initialized"**
   - Solution: Call `mcd_processor.initialize()` before using

### Debug Information

```python
# Check available drive types
print(f"Available drives: {mcd_processor.get_available_drives()}")

# Get drive-specific information
drive_info = mcd_processor.get_drive_info("iXA4")
print(f"Drive info: {drive_info}")

# Validate your configuration
validation = mcd_processor.validate_configuration_setup(
    specs_dict, electrical_dict, "iXA4"
)
print(f"Validation results: {validation}")

# Check initialization status
print(f"Initialized: {mcd_processor.processor.initialized}")
```

This updated architecture provides maximum flexibility with clean configuration separation while maintaining ease of use for common scenarios!
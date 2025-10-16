# Station Selection Feature Guide

## Overview

The Station Selection feature provides users with the ability to choose between automatic station assignment and manual station selection when running checkout tests. This enhancement gives users more control over which stations are used for their tests.

## Features

### 1. Automatic Assignment (Default)
- **How it works**: The system automatically assigns available stations based on the number of stages required
- **Use case**: When you don't need to use specific stations and want the quickest setup
- **Behavior**: Selects the first available stations in the system

### 2. Manual Selection
- **How it works**: Presents dropdown menus for each stage, allowing you to select specific stations
- **Use case**: When you need to use specific stations for testing or troubleshooting
- **Smart features**:
  - Shows only available stations in each dropdown
  - Updates other dropdowns when a station is selected (prevents conflicts)
  - Validates that all stages have unique station assignments

## How to Use

### Using the Station Selection Dialog

1. **Start a Test**: Click the "Run" button as usual
2. **Station Selection Dialog Opens**: A popup window will appear with two options:
   - "Automatically assign available stations" (default)
   - "Manually select stations"

### Automatic Assignment
1. Leave "Automatically assign available stations" selected (default)
2. Click "OK"
3. The system will assign available stations and proceed with the test

### Manual Selection
1. Select "Manually select stations"
2. Choose a station for each stage using the dropdown menus:
   - **Stage 1**: Select from available stations (e.g., ST01, ST02, etc.)
   - **Stage 2**: Select from remaining available stations
   - **Stage N**: Continue for all stages
3. Click "OK" to proceed with your selections

### Dialog Controls
- **OK**: Confirms your selection and proceeds with the test
- **Cancel**: Cancels the operation and returns to the main interface
- **X (Close)**: Same as Cancel

## Technical Details

### Station Availability
- The dialog only shows stations that are currently available (not in use by other tests)
- Station availability is checked in real-time when the dialog opens
- If a station becomes unavailable while the dialog is open, you'll be notified when trying to proceed

### Error Handling
- **Insufficient stations**: If there aren't enough available stations for automatic assignment, you'll be prompted to either wait or select stations manually
- **Station conflicts**: The system prevents selecting the same station for multiple stages
- **Incomplete selection**: You must select a station for every stage before proceeding
- **Station unavailable**: If a manually selected station becomes unavailable, you'll be notified to make a different selection

### Integration with Existing Workflow
- The feature seamlessly integrates with the existing test workflow
- All existing functionality remains unchanged
- Station release and management continue to work as before

## Files Modified/Added

### New Files
- `station_selection_dialog.py`: Contains the StationSelectionDialog class and related functionality
- `test_station_selection.py`: Test script for verifying the dialog functionality
- `STATION_SELECTION_GUIDE.md`: This documentation file

### Modified Files
- `UI.py`: Updated `start_test_thread()` function to use the new dialog
  - Added import for the station selection dialog
  - Replaced direct station allocation with dialog-based selection
  - Maintains backward compatibility with existing error handling

## API Reference

### `show_station_selection_dialog(parent, num_stations, program_id, serial_number)`

Shows the station selection dialog and returns the user's selection.

**Parameters:**
- `parent`: Parent tkinter window
- `num_stations`: Number of stations needed for the test
- `program_id`: Unique identifier for the test program
- `serial_number`: Serial number for tracking purposes

**Returns:**
- `dict`: `{"mode": "auto"|"manual", "stations": [list of station names]}` if confirmed
- `None`: if cancelled

**Example:**
```python
result = show_station_selection_dialog(window, 2, 12345, "SN001")
if result:
    mode = result["mode"]  # "auto" or "manual"
    stations = result["stations"]  # e.g., ["ST01", "ST02"]
```

### `StationSelectionDialog` Class

Main dialog class that handles the UI and logic for station selection.

**Key Methods:**
- `__init__(parent, num_stations, program_id, serial_number)`: Initialize dialog
- `show()`: Display dialog and return result
- `_update_station_options()`: Update dropdown options based on availability
- `_on_mode_change()`: Handle switching between auto and manual modes

## Testing

### Manual Testing
1. Run `test_station_selection.py` to test the dialog independently
2. Try both automatic and manual modes
3. Test with different numbers of stations
4. Test error conditions (insufficient stations, etc.)

### Integration Testing
1. Run the main UI application
2. Set different numbers of stages in the "Number of Stages" field
3. Click "Run" and test both assignment modes
4. Verify that station allocation and release work correctly

## Troubleshooting

### Common Issues

**Dialog doesn't appear:**
- Ensure the station manager is properly initialized
- Check that the import statement for `station_selection_dialog` is correct

**No stations available in dropdowns:**
- Verify that stations are properly configured in the station manager
- Check station connectivity and status

**"Station manager not initialized" error:**
- Make sure `set_station_manager()` is called during application startup
- Verify the station manager is started with `station_manager.start()`

### Debug Information
The dialog provides console output for debugging:
- Station allocation results
- Selection mode information
- Error messages for troubleshooting

## Future Enhancements

Potential improvements that could be added:

1. **Station Preferences**: Save user's preferred station assignments
2. **Station Status Display**: Show station status (free, in-use, offline) in dropdowns
3. **Station Information**: Display additional station details (IP, capabilities)
4. **Quick Selection**: Buttons for common station assignment patterns
5. **Station Groups**: Ability to define and select pre-configured station groups

## Support

For issues or questions about the station selection feature:
1. Check this documentation first
2. Run the test script to isolate issues
3. Check the console output for error messages
4. Verify station manager configuration and connectivity
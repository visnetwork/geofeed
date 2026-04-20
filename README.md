# GPON Network Design Script

This repository contains a QGIS Python script for designing GPON (Gigabit Passive Optical Network) infrastructure with automatic NAP (Network Access Point) to FDT (Fiber Distribution Terminal) assignment using shortest path routing.

## Files

- `gpon-nap-to-fdt-shortest-stable-v6.3-claude.py` - Main GPON network design script
- `requirements.txt` - Python dependencies
- `geofeed.csv` - IP geolocation data (geofeed format)

## Features

### Enhanced Street Network Recognition
- **Dynamic street layer refresh** - Forces reload of street data to include newly added features
- **Real-time street recognition** - Newly drawn streets are automatically included in routing calculations
- **Comprehensive validation** - Validates all input layers and provides detailed feedback
- **Error handling** - Graceful handling of invalid geometries and disconnected networks

### Network Analysis
- **NetworkX integration** - Uses industry-standard graph algorithms for optimal routing
- **Shortest path calculation** - Dijkstra's algorithm for finding optimal NAP-FDT connections
- **Multi-geometry support** - Handles both LineString and MultiLineString street geometries
- **Distance-weighted routing** - Considers actual distances for realistic path planning

### QGIS Integration
- **Native QGIS APIs** - Full integration with QGIS vector layers and processing
- **Progress feedback** - Real-time progress reporting during processing
- **Automatic layer creation** - Creates output connection layers automatically
- **Spatial indexing** - Efficient spatial operations for large datasets

## Requirements

### Software Requirements
- QGIS 3.x with Python support
- Python 3.6 or later

### Python Dependencies
```bash
pip install -r requirements.txt
```

The main dependency is:
- `networkx>=3.0` - Graph analysis library for shortest path calculations

## Usage

### Prerequisites
1. Open your QGIS project containing the required layers
2. Ensure you have the following layers in your project:
   - **Streets layer** (LineString geometry) - Street network for routing
   - **NAPs layer** (Point geometry) - Network Access Points to be connected
   - **FDTs layer** (Point geometry) - Fiber Distribution Terminals

### Running the Script

#### Option 1: QGIS Python Console
1. Open QGIS Python Console (Plugins → Python Console)
2. Load and run the script:
```python
exec(open('/path/to/gpon-nap-to-fdt-shortest-stable-v6.3-claude.py').read())
run_gpon_network_design()
```

#### Option 2: QGIS Script Runner
1. Open Processing Toolbox (Processing → Toolbox)
2. Navigate to Scripts → Tools → Open Existing Script
3. Select `gpon-nap-to-fdt-shortest-stable-v6.3-claude.py`
4. Run the script

#### Option 3: Customize Layer Names
If your layers have different names, modify the script parameters:
```python
from gpon_nap_to_fdt_shortest_stable_v6_3_claude import GPONNetworkDesigner
from qgis.core import QgsProcessingFeedback

feedback = QgsProcessingFeedback()
designer = GPONNetworkDesigner(feedback)

success = designer.run_complete_workflow(
    streets_layer_name="Your_Streets_Layer",
    naps_layer_name="Your_NAPs_Layer", 
    fdts_layer_name="Your_FDTs_Layer",
    output_layer_name="Custom_Connections"
)
```

## Key Improvements

This enhanced version addresses the critical issue where **newly added streets were not being recognized** in network routing calculations:

### Before (Original Issue)
- Street network graph was built once at script start
- New streets added to layer after processing were ignored
- Resulted in suboptimal routing missing new infrastructure
- No validation of street layer completeness

### After (Enhanced Version)
- **Forces refresh** of street layer before processing (`force_refresh_layer()`)
- **Validates all features** are loaded and processed
- **Dynamic recognition** of newly added streets
- **Comprehensive logging** shows exactly how many streets are processed
- **Error handling** for invalid geometries
- **Performance tracking** for optimization

### Technical Enhancements
1. **Layer Refresh Mechanism**: `force_refresh_layer()` forces QGIS to reload layer data
2. **Feature Validation**: Ensures all current features are included in processing
3. **Enhanced Logging**: Detailed progress reporting and statistics
4. **Error Recovery**: Graceful handling of invalid or problematic geometries
5. **Network Validation**: Checks for disconnected components and provides warnings

## Output

The script creates a new vector layer `NAP_FDT_Connections` containing:
- **LineString geometries** showing optimal paths between NAPs and FDTs
- **Attributes**:
  - `nap_id` - Source NAP feature ID
  - `fdt_id` - Target FDT feature ID  
  - `distance` - Total path distance in meters
  - `path_length` - Number of path segments

## Troubleshooting

### Common Issues

**"Layer not found" errors**:
- Ensure layer names match exactly (case-sensitive)
- Check layers are loaded in current QGIS project

**"No valid street network" errors**:
- Verify street layer contains LineString geometries
- Check for disconnected street segments
- Ensure street layer is not empty

**"NetworkX import failed" errors**:
```bash
pip install networkx
```

**Performance issues with large datasets**:
- The script processes streets in batches with progress updates
- Consider simplifying complex street geometries
- Use spatial indexing for very large datasets

### Logging
Check the QGIS Message Log (View → Panels → Log Messages) for detailed processing information and error messages.

## License

MIT License - Feel free to use and modify for your GPON network design needs.
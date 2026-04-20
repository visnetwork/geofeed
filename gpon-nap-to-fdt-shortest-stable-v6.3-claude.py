#!/usr/bin/env python3
"""
GPON Network Design Script - NAP to FDT Assignment with Shortest Path Routing
Version: 6.3 Claude Enhanced

This script assigns Network Access Points (NAPs) to Fiber Distribution Terminals (FDTs)
using shortest path algorithms through street networks. It includes enhanced functionality
to recognize newly added streets and refresh network data dynamically.

Key Features:
- Dynamic street network graph building with refresh capability
- Shortest path routing between NAPs and FDTs
- Recognition of newly added streets in real-time
- Comprehensive logging and validation
- Error handling for invalid geometries
- QGIS integration with proper feedback mechanisms

Author: Claude AI Enhanced Version
License: MIT
"""

import sys
import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, QgsLineString,
    QgsProcessingFeedback, QgsWkbTypes, QgsDistanceArea, QgsCoordinateReferenceSystem,
    QgsFeatureRequest, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils,
    QgsSpatialIndex, QgsPointXY, QgsApplication, QgsMessageLog, Qgis
)
from qgis.analysis import QgsNetworkAnalyzer
from PyQt5.QtCore import QVariant
import networkx as nx
import math
from typing import Dict, List, Tuple, Optional, Set
import time
import traceback


class GPONNetworkDesigner:
    """
    Main class for GPON network design and NAP to FDT assignment.
    
    This class handles the complete workflow of:
    1. Loading and validating input layers
    2. Building dynamic street network graphs
    3. Finding optimal paths between NAPs and FDTs
    4. Creating output connection features
    """
    
    def __init__(self, feedback: QgsProcessingFeedback = None):
        """Initialize the GPON Network Designer.
        
        Args:
            feedback: QGIS processing feedback object for progress reporting
        """
        self.feedback = feedback or QgsProcessingFeedback()
        self.project = QgsProject.instance()
        self.distance_calc = QgsDistanceArea()
        self.network_graph = None
        self.point_to_node = {}
        self.node_id_counter = 0
        self.processed_streets_count = 0
        self.total_streets_count = 0
        
        # Performance tracking
        self.start_time = time.time()
        self.step_times = {}
        
        # Configure distance calculator
        crs = self.project.crs() if self.project else QgsCoordinateReferenceSystem("EPSG:4326")
        self.distance_calc.setSourceCrs(crs, QgsProject.instance().transformContext())
        self.distance_calc.setEllipsoid(crs.ellipsoidAcronym())
        
    def log_message(self, message: str, level: Qgis.MessageLevel = Qgis.Info):
        """Log message to both feedback and QGIS message log.
        
        Args:
            message: Message to log
            level: Message level (Info, Warning, Critical)
        """
        if self.feedback:
            self.feedback.pushInfo(message)
        QgsMessageLog.logMessage(message, "GPON Network Designer", level)
        
    def log_step_time(self, step_name: str):
        """Log time taken for a processing step.
        
        Args:
            step_name: Name of the processing step
        """
        current_time = time.time()
        if hasattr(self, 'last_step_time'):
            elapsed = current_time - self.last_step_time
            self.step_times[step_name] = elapsed
            self.log_message(f"{step_name} completed in {elapsed:.2f} seconds")
        self.last_step_time = current_time
        
    def force_refresh_layer(self, layer: QgsVectorLayer) -> bool:
        """Force refresh of vector layer to ensure all features are loaded.
        
        Args:
            layer: Vector layer to refresh
            
        Returns:
            bool: True if refresh successful, False otherwise
        """
        try:
            if not layer or not layer.isValid():
                self.log_message(f"Invalid layer provided for refresh", Qgis.Warning)
                return False
                
            # Force reload from data source
            layer.reload()
            
            # Clear any cached feature counts
            layer.featureCount()
            
            # Trigger repaint to ensure data is loaded
            layer.triggerRepaint()
            
            # Wait a moment for the refresh to complete
            QgsApplication.processEvents()
            
            self.log_message(f"Successfully refreshed layer: {layer.name()}")
            return True
            
        except Exception as e:
            self.log_message(f"Error refreshing layer {layer.name()}: {str(e)}", Qgis.Critical)
            return False
            
    def validate_layer(self, layer: QgsVectorLayer, layer_name: str, 
                      expected_geometry_type: QgsWkbTypes.GeometryType) -> bool:
        """Validate that a layer exists and has the expected geometry type.
        
        Args:
            layer: Vector layer to validate
            layer_name: Human-readable name for error messages
            expected_geometry_type: Expected geometry type
            
        Returns:
            bool: True if layer is valid, False otherwise
        """
        if not layer:
            self.log_message(f"{layer_name} layer not found", Qgis.Critical)
            return False
            
        if not layer.isValid():
            self.log_message(f"{layer_name} layer is not valid", Qgis.Critical)
            return False
            
        if layer.geometryType() != expected_geometry_type:
            expected_name = QgsWkbTypes.geometryDisplayString(expected_geometry_type)
            actual_name = QgsWkbTypes.geometryDisplayString(layer.geometryType())
            self.log_message(
                f"{layer_name} layer has wrong geometry type. Expected: {expected_name}, "
                f"Got: {actual_name}", Qgis.Critical
            )
            return False
            
        feature_count = layer.featureCount()
        if feature_count == 0:
            self.log_message(f"{layer_name} layer contains no features", Qgis.Warning)
            return False
            
        self.log_message(f"{layer_name} layer validated successfully ({feature_count} features)")
        return True
        
    def build_street_network_graph(self, streets_layer: QgsVectorLayer) -> bool:
        """Build NetworkX graph from streets layer with enhanced refresh and validation.
        
        This is the core method that addresses the issue of newly added streets
        not being recognized. It forces a refresh of the streets layer before
        processing to ensure all current features are included.
        
        Args:
            streets_layer: Vector layer containing street geometries
            
        Returns:
            bool: True if graph built successfully, False otherwise
        """
        self.log_message("Step 1: Building street network graph...")
        step_start_time = time.time()
        
        try:
            # Force refresh of streets layer to include newly added features
            if not self.force_refresh_layer(streets_layer):
                return False
                
            # Validate the streets layer
            if not self.validate_layer(streets_layer, "Streets", QgsWkbTypes.LineGeometry):
                return False
                
            # Initialize network graph and node tracking
            self.network_graph = nx.Graph()
            self.point_to_node = {}
            self.node_id_counter = 0
            
            # Get current feature count after refresh
            self.total_streets_count = streets_layer.featureCount()
            self.processed_streets_count = 0
            
            self.log_message(f"Processing {self.total_streets_count} streets from layer...")
            
            # Create spatial index for efficient processing
            spatial_index = QgsSpatialIndex()
            
            # Process each street feature
            for current_feature_num, street_feature in enumerate(streets_layer.getFeatures(), 1):
                try:
                    geometry = street_feature.geometry()
                    if not geometry or geometry.isNull():
                        self.log_message(f"Street feature {street_feature.id()} has null geometry", Qgis.Warning)
                        continue
                        
                    if geometry.wkbType() != QgsWkbTypes.LineString and geometry.wkbType() != QgsWkbTypes.MultiLineString:
                        self.log_message(f"Street feature {street_feature.id()} has unsupported geometry type", Qgis.Warning)
                        continue
                        
                    # Convert to line string if multi-line
                    if geometry.wkbType() == QgsWkbTypes.MultiLineString:
                        multi_line = geometry.asMultiPolyline()
                        for line in multi_line:
                            self._process_line_geometry(line, street_feature.id())
                    else:
                        line = geometry.asPolyline()
                        self._process_line_geometry(line, street_feature.id())
                        
                    self.processed_streets_count += 1
                    
                    # Update progress every 100 features
                    if current_feature_num % 100 == 0:
                        progress = int((current_feature_num / self.total_streets_count) * 100)
                        self.feedback.setProgress(progress)
                        self.log_message(f"Processed {current_feature_num}/{self.total_streets_count} streets...")
                        
                except Exception as e:
                    self.log_message(f"Error processing street feature {street_feature.id()}: {str(e)}", Qgis.Warning)
                    continue
                    
            # Validate graph construction
            node_count = self.network_graph.number_of_nodes()
            edge_count = self.network_graph.number_of_edges()
            
            if node_count == 0:
                self.log_message("No valid street network nodes created", Qgis.Critical)
                return False
                
            if edge_count == 0:
                self.log_message("No valid street network edges created", Qgis.Critical)
                return False
                
            # Log final statistics
            elapsed_time = time.time() - step_start_time
            self.log_message(f"Street network graph built successfully:")
            self.log_message(f"  - Processed streets: {self.processed_streets_count}/{self.total_streets_count}")
            self.log_message(f"  - Network nodes: {node_count}")
            self.log_message(f"  - Network edges: {edge_count}")
            self.log_message(f"  - Processing time: {elapsed_time:.2f} seconds")
            
            # Check for disconnected components
            connected_components = list(nx.connected_components(self.network_graph))
            if len(connected_components) > 1:
                self.log_message(f"Warning: Street network has {len(connected_components)} disconnected components", Qgis.Warning)
                largest_component_size = max(len(component) for component in connected_components)
                self.log_message(f"Largest connected component has {largest_component_size} nodes")
                
            return True
            
        except Exception as e:
            self.log_message(f"Critical error building street network graph: {str(e)}", Qgis.Critical)
            self.log_message(f"Traceback: {traceback.format_exc()}")
            return False
            
    def _process_line_geometry(self, line_points: List[QgsPointXY], feature_id: int):
        """Process a line geometry and add nodes/edges to the network graph.
        
        Args:
            line_points: List of points defining the line
            feature_id: ID of the source feature
        """
        if len(line_points) < 2:
            return
            
        prev_node_id = None
        
        for point in line_points:
            # Create unique key for point (rounded to avoid floating point issues)
            point_key = (round(point.x(), 6), round(point.y(), 6))
            
            # Get or create node ID for this point
            if point_key in self.point_to_node:
                node_id = self.point_to_node[point_key]
            else:
                node_id = self.node_id_counter
                self.point_to_node[point_key] = node_id
                self.network_graph.add_node(node_id, x=point.x(), y=point.y())
                self.node_id_counter += 1
                
            # Add edge between consecutive points
            if prev_node_id is not None:
                # Calculate edge weight (distance)
                prev_point = QgsPointXY(
                    self.network_graph.nodes[prev_node_id]['x'],
                    self.network_graph.nodes[prev_node_id]['y']
                )
                current_point = QgsPointXY(point.x(), point.y())
                distance = self.distance_calc.measureLine(prev_point, current_point)
                
                # Add edge with weight
                self.network_graph.add_edge(prev_node_id, node_id, weight=distance, feature_id=feature_id)
                
            prev_node_id = node_id
            
    def find_nearest_network_node(self, point: QgsPointXY) -> Optional[int]:
        """Find the nearest node in the network graph to a given point.
        
        Args:
            point: Point to find nearest node for
            
        Returns:
            Optional[int]: Node ID of nearest node, or None if not found
        """
        if not self.network_graph or self.network_graph.number_of_nodes() == 0:
            return None
            
        min_distance = float('inf')
        nearest_node = None
        
        for node_id in self.network_graph.nodes():
            node_data = self.network_graph.nodes[node_id]
            node_point = QgsPointXY(node_data['x'], node_data['y'])
            distance = self.distance_calc.measureLine(point, node_point)
            
            if distance < min_distance:
                min_distance = distance
                nearest_node = node_id
                
        return nearest_node
        
    def calculate_shortest_path(self, start_point: QgsPointXY, end_point: QgsPointXY) -> Optional[List[QgsPointXY]]:
        """Calculate shortest path between two points using the street network.
        
        Args:
            start_point: Starting point
            end_point: Ending point
            
        Returns:
            Optional[List[QgsPointXY]]: List of points defining the path, or None if no path found
        """
        if not self.network_graph:
            self.log_message("Network graph not initialized", Qgis.Warning)
            return None
            
        # Find nearest nodes to start and end points
        start_node = self.find_nearest_network_node(start_point)
        end_node = self.find_nearest_network_node(end_point)
        
        if start_node is None or end_node is None:
            self.log_message("Could not find nearest network nodes for path calculation", Qgis.Warning)
            return None
            
        try:
            # Calculate shortest path using Dijkstra's algorithm
            path_nodes = nx.shortest_path(self.network_graph, start_node, end_node, weight='weight')
            
            # Convert node path to point path
            path_points = []
            for node_id in path_nodes:
                node_data = self.network_graph.nodes[node_id]
                path_points.append(QgsPointXY(node_data['x'], node_data['y']))
                
            return path_points
            
        except nx.NetworkXNoPath:
            self.log_message(f"No path found between nodes {start_node} and {end_node}", Qgis.Warning)
            return None
        except Exception as e:
            self.log_message(f"Error calculating shortest path: {str(e)}", Qgis.Warning)
            return None
            
    def assign_naps_to_fdts(self, naps_layer: QgsVectorLayer, fdts_layer: QgsVectorLayer) -> List[Dict]:
        """Assign NAPs to FDTs using shortest path routing.
        
        Args:
            naps_layer: Vector layer containing NAP points
            fdts_layer: Vector layer containing FDT points
            
        Returns:
            List[Dict]: List of assignment dictionaries with NAP, FDT, and path information
        """
        self.log_message("Step 2: Assigning NAPs to FDTs using shortest paths...")
        
        assignments = []
        
        if not self.validate_layer(naps_layer, "NAPs", QgsWkbTypes.PointGeometry):
            return assignments
            
        if not self.validate_layer(fdts_layer, "FDTs", QgsWkbTypes.PointGeometry):
            return assignments
            
        # Force refresh of both layers to ensure newly added features are included
        self.force_refresh_layer(naps_layer)
        self.force_refresh_layer(fdts_layer)
        
        nap_count = naps_layer.featureCount()
        fdt_count = fdts_layer.featureCount()
        
        self.log_message(f"Processing {nap_count} NAPs and {fdt_count} FDTs...")
        
        # Process each NAP
        for nap_num, nap_feature in enumerate(naps_layer.getFeatures(), 1):
            try:
                nap_geometry = nap_feature.geometry()
                if not nap_geometry or nap_geometry.isNull():
                    continue
                    
                nap_point = nap_geometry.asPoint()
                best_assignment = None
                shortest_distance = float('inf')
                
                # Find best FDT for this NAP
                for fdt_feature in fdts_layer.getFeatures():
                    try:
                        fdt_geometry = fdt_feature.geometry()
                        if not fdt_geometry or fdt_geometry.isNull():
                            continue
                            
                        fdt_point = fdt_geometry.asPoint()
                        
                        # Calculate shortest path
                        path_points = self.calculate_shortest_path(nap_point, fdt_point)
                        
                        if path_points:
                            # Calculate total path distance
                            total_distance = 0
                            for i in range(len(path_points) - 1):
                                segment_distance = self.distance_calc.measureLine(path_points[i], path_points[i + 1])
                                total_distance += segment_distance
                                
                            if total_distance < shortest_distance:
                                shortest_distance = total_distance
                                best_assignment = {
                                    'nap_id': nap_feature.id(),
                                    'fdt_id': fdt_feature.id(),
                                    'nap_point': nap_point,
                                    'fdt_point': fdt_point,
                                    'path_points': path_points,
                                    'distance': total_distance
                                }
                                
                    except Exception as e:
                        self.log_message(f"Error processing FDT {fdt_feature.id()}: {str(e)}", Qgis.Warning)
                        continue
                        
                if best_assignment:
                    assignments.append(best_assignment)
                    self.log_message(f"NAP {nap_feature.id()} assigned to FDT {best_assignment['fdt_id']} "
                                   f"(distance: {best_assignment['distance']:.2f}m)")
                else:
                    self.log_message(f"Could not find path for NAP {nap_feature.id()}", Qgis.Warning)
                    
                # Update progress
                progress = int((nap_num / nap_count) * 100)
                self.feedback.setProgress(progress)
                
            except Exception as e:
                self.log_message(f"Error processing NAP {nap_feature.id()}: {str(e)}", Qgis.Warning)
                continue
                
        self.log_message(f"Completed NAP to FDT assignment: {len(assignments)} successful assignments")
        return assignments
        
    def create_connection_layer(self, assignments: List[Dict], output_layer_name: str = "NAP_FDT_Connections") -> Optional[QgsVectorLayer]:
        """Create a new layer with connection lines showing NAP to FDT assignments.
        
        Args:
            assignments: List of assignment dictionaries
            output_layer_name: Name for the output layer
            
        Returns:
            Optional[QgsVectorLayer]: Created layer or None if failed
        """
        if not assignments:
            self.log_message("No assignments to create connections for", Qgis.Warning)
            return None
            
        try:
            # Create new vector layer
            crs = self.project.crs()
            layer = QgsVectorLayer(f"LineString?crs={crs.authid()}", output_layer_name, "memory")
            
            if not layer.isValid():
                self.log_message("Failed to create output layer", Qgis.Critical)
                return None
                
            # Add fields
            provider = layer.dataProvider()
            from qgis.core import QgsField
            provider.addAttributes([
                QgsField("nap_id", QVariant.Int),
                QgsField("fdt_id", QVariant.Int),
                QgsField("distance", QVariant.Double),
                QgsField("path_length", QVariant.Int)
            ])
            layer.updateFields()
            
            # Add features
            features = []
            for assignment in assignments:
                feature = QgsFeature()
                
                # Create line geometry from path points
                line_geometry = QgsGeometry.fromPolylineXY(assignment['path_points'])
                feature.setGeometry(line_geometry)
                
                # Set attributes
                feature.setAttributes([
                    assignment['nap_id'],
                    assignment['fdt_id'],
                    assignment['distance'],
                    len(assignment['path_points'])
                ])
                
                features.append(feature)
                
            provider.addFeatures(features)
            layer.updateExtents()
            
            # Add to project
            self.project.addMapLayer(layer)
            
            self.log_message(f"Created connection layer '{output_layer_name}' with {len(features)} connections")
            return layer
            
        except Exception as e:
            self.log_message(f"Error creating connection layer: {str(e)}", Qgis.Critical)
            return None
            
    def run_complete_workflow(self, streets_layer_name: str, naps_layer_name: str, 
                            fdts_layer_name: str, output_layer_name: str = "NAP_FDT_Connections") -> bool:
        """Run the complete GPON network design workflow.
        
        Args:
            streets_layer_name: Name of streets layer in QGIS project
            naps_layer_name: Name of NAPs layer in QGIS project  
            fdts_layer_name: Name of FDTs layer in QGIS project
            output_layer_name: Name for output connections layer
            
        Returns:
            bool: True if workflow completed successfully, False otherwise
        """
        self.log_message("Starting GPON Network Design Workflow...")
        self.log_message("=" * 60)
        
        try:
            # Get layers from project
            streets_layer = None
            naps_layer = None
            fdts_layer = None
            
            for layer in self.project.mapLayers().values():
                if layer.name() == streets_layer_name:
                    streets_layer = layer
                elif layer.name() == naps_layer_name:
                    naps_layer = layer
                elif layer.name() == fdts_layer_name:
                    fdts_layer = layer
                    
            # Validate all layers exist
            if not streets_layer:
                self.log_message(f"Streets layer '{streets_layer_name}' not found in project", Qgis.Critical)
                return False
                
            if not naps_layer:
                self.log_message(f"NAPs layer '{naps_layer_name}' not found in project", Qgis.Critical)
                return False
                
            if not fdts_layer:
                self.log_message(f"FDTs layer '{fdts_layer_name}' not found in project", Qgis.Critical)
                return False
                
            # Step 1: Build street network graph with refresh capability
            if not self.build_street_network_graph(streets_layer):
                self.log_message("Failed to build street network graph", Qgis.Critical)
                return False
                
            self.log_step_time("Street Network Graph Building")
            
            # Step 2: Assign NAPs to FDTs
            assignments = self.assign_naps_to_fdts(naps_layer, fdts_layer)
            if not assignments:
                self.log_message("No successful NAP to FDT assignments created", Qgis.Critical)
                return False
                
            self.log_step_time("NAP to FDT Assignment")
            
            # Step 3: Create connection layer
            connection_layer = self.create_connection_layer(assignments, output_layer_name)
            if not connection_layer:
                self.log_message("Failed to create connection layer", Qgis.Critical)
                return False
                
            self.log_step_time("Connection Layer Creation")
            
            # Log final summary
            total_time = time.time() - self.start_time
            self.log_message("=" * 60)
            self.log_message("GPON Network Design Workflow Completed Successfully!")
            self.log_message(f"Total processing time: {total_time:.2f} seconds")
            self.log_message(f"Streets processed: {self.processed_streets_count}/{self.total_streets_count}")
            self.log_message(f"Successful connections: {len(assignments)}")
            self.log_message(f"Output layer: {output_layer_name}")
            
            return True
            
        except Exception as e:
            self.log_message(f"Critical error in workflow: {str(e)}", Qgis.Critical)
            self.log_message(f"Traceback: {traceback.format_exc()}")
            return False


# Main execution function for QGIS Script Runner
def run_gpon_network_design():
    """Main function to run GPON network design with default layer names."""
    
    # Initialize feedback for standalone execution
    feedback = QgsProcessingFeedback()
    
    # Create designer instance
    designer = GPONNetworkDesigner(feedback)
    
    # Default layer names - modify these based on your QGIS project
    streets_layer_name = "Streets"
    naps_layer_name = "NAPs" 
    fdts_layer_name = "FDTs"
    output_layer_name = "NAP_FDT_Connections"
    
    # Run the complete workflow
    success = designer.run_complete_workflow(
        streets_layer_name, 
        naps_layer_name,
        fdts_layer_name, 
        output_layer_name
    )
    
    if success:
        print("GPON Network Design completed successfully!")
    else:
        print("GPON Network Design failed - check QGIS message log for details")
        
    return success


# For direct script execution
if __name__ == "__main__":
    # Check if running in QGIS environment
    try:
        from qgis.core import QgsApplication
        if QgsApplication.instance() is None:
            print("This script must be run within QGIS environment")
            sys.exit(1)
            
        run_gpon_network_design()
        
    except ImportError:
        print("QGIS Python environment not available")
        sys.exit(1)
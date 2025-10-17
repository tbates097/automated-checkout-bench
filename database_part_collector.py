# -*- coding: utf-8 -*-
"""
Database Part Results Collector

This module handles collecting and exporting test results for individual stations/parts
to JSON format for database population. Each station generates its own database record.

@author: TBates
"""

import json
import datetime
import os
from typing import Dict, List, Any, Optional

class PartResultsCollector:
    """
    Collects and exports test results for individual stations/parts.
    Each station creates a unique JSON file for database population.
    """
    
    def __init__(self, job_number: str, station: str, operator: str, stage_type: str, 
                 comments: str, test_axes: List[str], folder: str, part_number: str = None):
        """
        Initialize the part results collector for a specific station.
        
        Args:
            job_number: The serial number for this specific part (e.g., "ABC123456")
            station: Station identifier (e.g., 'ST01', 'ST02')
            operator: Operator employee number performing the test
            stage_type: Type of stage being tested
            comments: Test comments
            test_axes: List of all axes being tested in this job
            folder: Output folder for results
            part_number: Parsed part number from smart string (e.g., "PRO165LM")
        """
        self.serial_number = job_number  # This is now the individual serial number
        self.job_number = job_number[:6] if len(job_number) >= 6 else job_number  # Extract 6-digit job number
        self.station = station
        self.operator = operator
        self.stage_type = stage_type
        self.part_number = part_number or stage_type  # Use parsed part number or fallback to stage_type
        self.comments = comments
        self.test_axes = test_axes
        self.folder = folder
        
        # Generate stage serial number in required format (xxxxxx-xx)
        self.stage_serial_number = self._generate_stage_serial_number()
        
        # Initialize test timing
        self.test_start_time = datetime.datetime.now()
        self.test_end_time = None
        self.test_complete = False
        
        # Initialize data containers with new flat structure
        self.hall_method = None
        self.hall_result_passed = None
        self.commutation_offset = None
        
        # Position data
        self.ccw_limit_position = None
        self.cw_limit_position = None
        self.ccw_hardstop_position = None
        self.cw_hardstop_position = None
        
        # Distance data
        self.limit_to_limit_distance = None
        self.hardstop_to_hardstop_distance = None
        self.marker_to_limit_distance = None
        
        # Current analysis
        self.peak_running_current = None
        self.rms_running_current = None
        
        # Fault and rework data (simplified for flat structure)
        self.faults_occurred = False
        self.fault_type = None
        self.fault_timestamp = None
        self.fault_resolved = None
        
        self.rework_issue = None
        self.rework_solution = None
        self.rework_timestamp = None
        self.rework_emp_number = None
    
    def _generate_stage_serial_number(self) -> str:
        """
        Generate stage serial number in required format (xxxxxx-xx) based on station position.
        
        Returns:
            Stage serial number (e.g., 'ABC123-01')
        """
        try:
            # Find the position of this station in the sorted test_axes list
            sorted_axes = sorted(self.test_axes)
            station_index = sorted_axes.index(self.station) + 1
            return f"{self.job_number}-{station_index:02d}"
        except ValueError:
            # Fallback: extract number from station name
            station_num = ''.join(filter(str.isdigit, self.station))
            return f"{self.job_number}-{station_num:0>2}"
    
    def set_halls_result(self, method: str, result: str):
        """
        Set halls test result for specified method.
        
        Args:
            method: 'fallback_method' or 'mset_method'
            result: 'Passed' or 'Failed'
        """
        # Map to new flat structure
        if method == 'fallback_method':
            self.hall_method = "Fallback Method"
        elif method == 'mset_method':
            self.hall_method = "MSET Method"
        
        self.hall_result_passed = (result == "Passed")
    
    def set_commutation_offset(self, offset: float):
        """Set commutation offset value."""
        self.commutation_offset = offset
    
    def set_positions(self, ccw_limit: float = None, cw_limit: float = None,
                     ccw_hardstop: float = None, cw_hardstop: float = None):
        """
        Set position values. Only updates provided values.
        
        Args:
            ccw_limit: Counter-clockwise limit position
            cw_limit: Clockwise limit position
            ccw_hardstop: Counter-clockwise hardstop position
            cw_hardstop: Clockwise hardstop position
        """
        if ccw_limit is not None:
            self.ccw_limit_position = ccw_limit
        if cw_limit is not None:
            self.cw_limit_position = cw_limit
        if ccw_hardstop is not None:
            self.ccw_hardstop_position = ccw_hardstop
        if cw_hardstop is not None:
            self.cw_hardstop_position = cw_hardstop
    
    def set_distances(self, limit_to_limit: float = None, 
                     hardstop_to_hardstop: float = None,
                     marker_to_limit: float = None):
        """
        Set distance measurements.
        
        Args:
            limit_to_limit: Distance between CW and CCW limits
            hardstop_to_hardstop: Distance between CW and CCW hardstops
            marker_to_limit: Distance from marker to limit
        """
        if limit_to_limit is not None:
            self.limit_to_limit_distance = limit_to_limit
        if hardstop_to_hardstop is not None:
            self.hardstop_to_hardstop_distance = hardstop_to_hardstop
        if marker_to_limit is not None:
            self.marker_to_limit_distance = marker_to_limit
    
    def set_current_analysis(self, peak_current: float = None, rms_current: float = None):
        """
        Set current analysis results.
        
        Args:
            peak_current: Peak-to-peak running current
            rms_current: RMS running current
        """
        if peak_current is not None:
            self.peak_running_current = peak_current
        if rms_current is not None:
            self.rms_running_current = rms_current
    
    def add_fault(self, fault_type: str, description: str, resolved: bool = False):
        """
        Add a fault occurrence to the record.
        
        Args:
            fault_type: Type of fault that occurred
            description: Detailed description of the fault
            resolved: Whether the fault was resolved
        """
        self.faults_occurred = True
        self.fault_type = fault_type
        self.fault_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.fault_resolved = resolved
    
    def add_rework(self, issue: str, solution: str, emp_number: int = None):
        """
        Add a rework entry to the record.
        
        Args:
            issue: Description of the issue that required rework
            solution: Solution/action taken to resolve the issue
            emp_number: Employee number performing rework (defaults to original operator)
        """
        self.rework_issue = issue
        self.rework_solution = solution
        self.rework_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.rework_emp_number = emp_number or self.operator
    
    def set_test_status(self, status: str):
        """
        Set the test status and end time.
        
        Args:
            status: 'Complete', 'Aborted', 'Failed', 'Partial', etc.
        """
        self.test_complete = (status.lower() == 'complete')
        self.test_end_time = datetime.datetime.now()
    
    def calculate_test_duration(self) -> float:
        """
        Calculate test duration in minutes.
        
        Returns:
            Duration in minutes, or 0 if test hasn't ended
        """
        if self.test_end_time is None:
            end_time = datetime.datetime.now()
        else:
            end_time = self.test_end_time
        
        duration = end_time - self.test_start_time
        return round(duration.total_seconds() / 60, 2)
    
    def get_database_json(self) -> dict:
        """
        Generate JSON object with all collected data for database population.
        Uses the new flat key/value structure as specified.
        
        Returns:
            dict: Complete database record as JSON-ready dictionary
        """
        # Ensure test has end time
        if self.test_end_time is None:
            self.test_end_time = datetime.datetime.now()
        
        # Build the complete data structure using exact keys specified
        data = {
            "StageSerialNumber": self.stage_serial_number,
            "JobNumber": self.job_number,
            "Station": self.station,
            "EmpNumber": int(self.operator) if str(self.operator).isdigit() else self.operator,
            "PartNumber": self.part_number,
            "TestDate": self.test_start_time.strftime("%Y-%m-%d"),
            "TestStartTime": self.test_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "TestEndTime": self.test_end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "TestDuration": self.calculate_test_duration(),
            "TestComplete": self.test_complete,
            "Comments": self.comments,
            
            "HallMethod": self.hall_method,
            "HallResultPassed": self.hall_result_passed,
            
            "CommutationOffset": self.commutation_offset,
            
            "CcwLimitPosition": self.ccw_limit_position,
            "CwLimitPosition": self.cw_limit_position,
            "CcwHardstopPosition": self.ccw_hardstop_position,
            "CwHardstopPosition": self.cw_hardstop_position,
            
            "LimitToLimitDistance": self.limit_to_limit_distance,
            "HardstopToHardstopDistance": self.hardstop_to_hardstop_distance,
            "MarkerToLimitDistance": self.marker_to_limit_distance,
            
            "PeakRunningCurrent": self.peak_running_current,
            "RmsRunningCurrent": self.rms_running_current,
            
            "FaultsOccurred": self.faults_occurred,
            "FaultType": self.fault_type,
            "FaultTimestamp": self.fault_timestamp,
            "Resolved": self.fault_resolved,
            
            "ReworkIssue": self.rework_issue,
            "ReworkSolution": self.rework_solution,
            "ReworkTimestamp": self.rework_timestamp,
            "ReworkEmpNumber": self.rework_emp_number
        }
        
        return data

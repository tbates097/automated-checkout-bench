# -*- coding: utf-8 -*-
"""
Created on Tue Oct 22 08:30:32 2024

@author: TBates
"""

import os
import sys
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import datetime

sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger

class Burn_In_Plotting():
    
    def __init__(self, axis_data, stage_type, encoder, burn_in_time, job, op, comments, folder, text_widget):
        self.axis_data = axis_data
        self.stage_type = stage_type
        self.encoder = encoder
        self.burn_in_time = burn_in_time
        self.job = job
        self.op = op
        self.comments = comments
        self.folder = folder
        self.text_widget = text_widget
        
        self.sample_rate = 1000
        # Extract available axes and cycles from the data
        self.available_axes, self.available_cycles = self.get_axes_and_cycles()
        
        self.text_logger = TextLogger(text_widget)
        sys.stdout = self.text_logger
        
    def get_axes_and_cycles(self):
        """
        Get the available axes and cycles from the axis_data.

        Returns:
            tuple: (list of axes, list of cycles)
        """
        axes = set()
        cycles = list(self.axis_data.keys())

        # Collect all unique axes across cycles
        for cycle_data in self.axis_data.values():
            axes.update(cycle_data.keys())

        return list(axes), cycles

    def generate_plots(self):
        """
        Automatically generate both individual plots for each axis and cycle,
        overlaid plots for each axis with all cycles, and FFT plots of current feedback.
        """
        for axis in self.available_axes:
            # Generate separate plots for each axis-cycle combination
            for cycle in self.available_cycles:
                if axis in self.axis_data[cycle]:
                    # Regular Plot of CurrentFeedback vs PositionFeedback
                    fig = self.create_subplot(axis, cycle)
                    position_feedback = self.axis_data[cycle][axis]['PositionFeedback']
                    current_feedback = self.axis_data[cycle][axis]['CurrentFeedback']
                    fig.add_trace(go.Scatter(
                        x=position_feedback,
                        y=current_feedback,
                        mode='lines',
                        name=f'Axis {axis} - Cycle {cycle}'
                    ))
                    self.add_info_tables(fig, axis, cycle)
                    self.save_plot(fig, axis, cycle)
    
                    # FFT Plot of CurrentFeedback
                    fft_fig = self.create_subplot(axis, cycle, is_fft=True)
                    fft_freqs, self.fft_magnitude = self.calculate_fft(current_feedback)
                    fft_fig.add_trace(go.Scatter(
                        x=fft_freqs,
                        y=self.fft_magnitude,
                        mode='lines',
                        name=f'FFT - Axis {axis} - Cycle {cycle}'
                    ))
                    self.add_info_tables(fft_fig, axis, cycle, is_fft=True)
                    self.save_plot(fft_fig, axis, f'{cycle}_FFT')
    
            # Generate an overlaid plot for all cycles for the current axis
            fig = self.create_subplot(axis, "all_cycles")
            for cycle in self.available_cycles:
                if axis in self.axis_data[cycle]:
                    position_feedback = self.axis_data[cycle][axis]['PositionFeedback']
                    current_feedback = self.axis_data[cycle][axis]['CurrentFeedback']
                    fig.add_trace(go.Scatter(
                        x=position_feedback,
                        y=current_feedback,
                        mode='lines',
                        name=f'Axis {axis} - Cycle {cycle}'
                    ))
            self.add_info_tables(fig, axis, "all_cycles")
            self.save_plot(fig, axis, "all_cycles")
            
        print(f"Plots saved in: {self.plot_folder}")
    
    def create_subplot(self, axis, cycle, is_fft=False):
        """
        Create a subplot with 3 rows: the first row for the plot and the bottom rows for tables.
        The title and axis labels adjust based on if the plot is an FFT.
        """
        fig = make_subplots(
            rows=2, cols=3,
            row_heights=[1.5, 0.5],
            vertical_spacing=0.1,
            specs=[[{"type": "scatter", "colspan": 3}, None, None],
                   [{"type": "table"}, {"type": "table"}, {"type": "table"}]]
        )
        title = f"FFT of CurrentFeedback for Axis {axis} - Cycle {cycle}" if is_fft else f"CurrentFeedback vs PositionFeedback for Axis {axis} - Cycle {cycle}"
        xaxis_title = "Frequency (Hz)" if is_fft else "PositionFeedback"
        yaxis_title = "Magnitude" if is_fft else "CurrentFeedback"
        
        fig.update_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title
        )
        return fig
    
    def add_info_tables(self, fig, axis, cycle, is_fft=False):
        """
        Add the results, comments, and test conditions tables to the figure.
        The info adjusts based on if the plot is an FFT.
        """
        self.current_date = datetime.date.today()
        self.current_time = datetime.datetime.now().time()
    
        if cycle == "all_cycles":
            current_feedback_all = []
            acceleration_command_all = []
    
            # Gather data from all cycles
            for cycle_num in self.available_cycles:
                if axis in self.axis_data[cycle_num]:
                    current_feedback_all.extend(self.axis_data[cycle_num][axis]['CurrentFeedback'])
                    acceleration_command_all.extend(self.axis_data[cycle_num][axis].get('AccelerationCommand', []))
    
            # Calculate peak-to-peak and RMS across all cycles
            peak_to_peak_value = self.calculate_peak_to_peak(current_feedback_all)
            rms_value = self.calculate_rms(current_feedback_all, acceleration_command_all)
            results_text = f'Current Feedback: {round(peak_to_peak_value, 4)} pk<br>RMS: {round(rms_value,4)}'

            fig.add_trace(go.Table(
                header=dict(values=["Results"], align='left'),
                cells=dict(values=[results_text.split('<br>')], align='left')), row=2, col=1)
        else:
            current_feedback = self.axis_data[cycle][axis]['CurrentFeedback']
            acceleration_command = self.axis_data[cycle][axis].get('AccelerationCommand', [])
            
            if is_fft:
                peak_to_peak_value = max(self.fft_magnitude)
                fft_text = f'FFT Magnitude pk: {round(peak_to_peak_value, 4)}' if peak_to_peak_value else 'N/A'
                results_text = f'{fft_text}'
            else:
                peak_to_peak_value = self.calculate_peak_to_peak(current_feedback)
                rms_value = self.calculate_rms(current_feedback, acceleration_command)
                results_text = f'Current Feedback: {round(peak_to_peak_value, 4)} pk<br>RMS: {round(rms_value,4)}'
            
            fig.add_trace(go.Table(
                header=dict(values=["Results"], align='left'),
                cells=dict(values=[results_text.split('<br>')], align='left')), row=2, col=1)

        # Comments Table
        comments = [
            ['Job Number', f'{str(self.job)}'],
            ['Stage', self.stage_type],
            ['Date', f'{self.current_date} {self.current_time}'],
            ['Operator', self.op],
            ['Comments', self.comments]
        ]
        fig.add_trace(go.Table(
            header=dict(values=["Field", "Value"], align="left"),
            cells=dict(values=[list(x) for x in zip(*comments)], align="left")), row=2, col=2)

        # Test Conditions Table
        degree_sign = u'\N{DEGREE SIGN}'
        conditions = [
            ['Temperature', f'{20} {degree_sign}C'],
            ['Burn-In Time', f'{self.burn_in_time} hours'],
            ['Encoder', f'{self.encoder}']
        ]
        fig.add_trace(go.Table(
            header=dict(values=["Condition", "Value"], align="left"),
            cells=dict(values=[list(x) for x in zip(*conditions)], align="left")), row=2, col=3)    # Comments and Test Conditions Tables (same as your existing logic)
    
    def calculate_fft(self, current_feedback):
        """
        Calculate the FFT of the current feedback signal.
        Returns frequency and magnitude arrays.
        """
        # Remove the DC component by subtracting the mean
        current_feedback = current_feedback - np.mean(current_feedback)
    
        n = len(current_feedback)
        fft_result = np.fft.fft(current_feedback)
        fft_freqs = np.fft.fftfreq(n, d=1/self.sample_rate)[:n//2]  # Correct frequency axis based on sample rate
        fft_magnitude = np.abs(fft_result[:n//2]) / n  # Normalize magnitude
        
        return fft_freqs, fft_magnitude
    
    def calculate_peak_to_peak(self, current_feedback):
        """
        Calculate the peak-to-peak value of the current feedback signal.

        Parameters:
            current_feedback (list): List of current feedback data points.

        Returns:
            float: Peak-to-peak value of the signal.
        """
        return np.ptp(current_feedback)

    def calculate_rms(self, current_feedback, acceleration_command):
        """
        Calculate the RMS of current feedback during constant velocity.

        Parameters:
            current_feedback (list): List of current feedback data points.
            acceleration_command (list): List of acceleration command data points.

        Returns:
            float: RMS value of the current feedback during constant velocity.
        """
        # Find indices where acceleration_command goes to zero
        zero_acceleration_indices = [i for i, a in enumerate(acceleration_command) if a == 0]

        # Filter current_feedback to only include values after acceleration command goes to zero
        if zero_acceleration_indices:
            current_feedback_after_accel = current_feedback[zero_acceleration_indices[0]:]
            return np.sqrt(np.mean(np.square(current_feedback_after_accel)))
        else:
            return 0  # Return 0 if no acceleration command goes to zero
    
    def save_plot(self, fig, axis, cycle):
        """
        Save the Plotly figure as an HTML file for the given axis and cycle.

        Parameters:
            fig (go.Figure): Plotly figure to save.
            axis (str): Axis name.
            cycle (int): Cycle number.
        """
        # Define the path for the plot folder inside self.folder
        self.plot_folder = os.path.join(self.folder, 'Plots')
        
        # Create the plot folder if it doesn't already exist
        if not os.path.exists(self.plot_folder):
            os.makedirs(self.plot_folder)
        
        # Create the file path for the plot
        self.plot_file = os.path.join(self.plot_folder, f'{self.job} Burn In Plot {axis}-{cycle}.html')

        # Save the figure as an interactive HTML file
        fig.write_html(self.plot_file)
    
    def run(self):
        """Run the Dash app."""
        self.app.run_server(debug=True, use_reloader=False)
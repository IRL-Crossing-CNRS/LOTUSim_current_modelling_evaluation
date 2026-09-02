## Gauss Markov currents plugin from UUVSim

This repository provides a Gauss-Markov process-based underwater current plugin for simulating ocean currents in a Gazebo environment. The plugin models the current velocity and direction (horizontal and vertical) using a Gauss-Markov process and publishes the simulated current data to a topic. This README guides you through the setup, build process, and simulation steps.

## Prerequisites

Before running the simulation, ensure you have the following installed:

    Gazebo: This simulation framework is required for running the model.
    CMake: Required for building the project.
    GCC/G++: C++ compiler for compiling the plugin code.

## Build instructions 

Navigate to the build directory in your project folder: `cd /path/to/gauss_markov_currents/build` 

Run the following commands to build the project:
- `cmake ..` 
- `make` 

After running these commands, the libGaussMarkov.so shared library will be built and ready to use.

**Simulation Setup**:


1. Setting up the Plugin

To use the plugin in a Gazebo simulation, in the first terminal, set the GZ_SIM_SYSTEM_PLUGIN_PATH environment variable to point to the folder where your plugin is built:
- Set the plugin path: `export GZ_SIM_SYSTEM_PLUGIN_PATH=<path/to>/gauss_markov_uuvsim/build/`

2. Start the simulation:
Run the following command to load the simulation with the specified SDF file (auv_controls_2.sdf):
- `gz sim '<path/to>/gauss_markov_uuvsim/auv_controls_2.sdf'`

3. Viewing Ocean Current Data

In the second terminal, this command display the current velocity and direction data as it's published by the plugin during the simulation:
- `gz topic -e -t \ocean_current`

## Configuration

The plugin can be configured via the **auv_controls_2.sdf** example file, where the ocean current parameters are set. The key configuration parameters are:

    constant_current: The section where the ocean current velocity and angles (horizontal and vertical) are defined.
    csv_output_file: Path to the CSV file where the ocean current data will be saved at predefined time milestones (6h, 12h, 18h, 24h).

Example snippet from **auv_controls_2.sdf**:

```sdf
<plugin name="gaussmarkov::UnderwaterCurrentPlugin" filename="libGaussMarkov.so">
  <namespace>hydrodynamics</namespace>
  <csv_output_file>/path/to/output.csv</csv_output_file>
  <constant_current>
    <topic>current_velocity</topic>
    <velocity>
      <mean>computed_uo_mean</mean>
      <min>0.001</min>
      <max>0.3</max>
      <mu>0.0</mu>
      <noiseAmp>0.01</noiseAmp>
    </velocity>
    <horizontal_angle>
      <mean>computed_horz_angle_mean</mean>
      <min>-3.0</min>
      <max>3.0</max>
      <mu>0</mu>
      <noiseAmp>0.01</noiseAmp>
    </horizontal_angle>
    <vertical_angle>
      <mean>computed_vert_angle_mean</mean>
      <min>-450.0</min>
      <max>140.0</max>
      <mu>0.0</mu>
      <noiseAmp>0.01</noiseAmp>
    </vertical_angle>
  </constant_current>
</plugin>
``` 

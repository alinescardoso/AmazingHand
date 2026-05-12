# Example control for the Pollen Robotics "AmazingHand" (a.k.a. AH!)

## How to use:
- Install Rust: https://www.rust-lang.org/tools/install
- Install uv: https://docs.astral.sh/uv/getting-started/installation/
- Install dora-rs: https://dora-rs.ai/docs/guides/Installation/installing
  - start the daemon: `dora up`

- Clone this repository and in a console from the directory run:
- `uv venv --python 3.12`
- To run the webcam hand tracking demo in simulation only:
  - `dora build dataflow_tracking_simu.yml --uv` (needs to be done only once)
  - `dora run dataflow_tracking_simu.yml --uv`
- To run the webcam hand tracking demo with real hardware:
  - `dora build dataflow_tracking_real.yml --uv` (needs to be done only once)
  - `dora run dataflow_tracking_real.yml --uv`
- To run a simple example to control the finger angles in simulation:
  - `dora build dataflow_angle_simu.yml --uv` (needs to be done only once)
  - `dora run dataflow_angle_simu.yml --uv`

## Windows one-shot installer (interactive)

From `Demo/`, run:

`powershell -ExecutionPolicy Bypass -File .\install_windows_real_demo.ps1`

Or double-click the portable launcher:

`Abrir_AmazingHand_Demo.cmd`

To create a Desktop icon on any PC (without hardcoded project path), run:

`powershell -ExecutionPolicy Bypass -File .\Criar_Atalho_AmazingHand.ps1`

This script:
- installs Rust and uv (via winget, if missing)
- installs Python 3.12 if missing
- installs dora-rs-cli
- creates the Python 3.12 virtual environment (`uv venv --python 3.12`)
- runs `uv sync` for Python modules (`HandTracking` and `AHSimulation`)
- lets you choose the available demo (`dataflow_*.yml`)
- lets you choose an available COM port (for demos that require serial)
- lets you choose a camera index (for demos that use HandTracking)
- updates the selected dataflow with the selected COM port when needed
- sets `AH_CAMERA_INDEX` for the hand tracker camera index
- opens a graphical setup window (dropdowns for demo, COM and camera)
- uses defaults: `dataflow_tracking_real.yml`, `COM3`, `camera 0`
- for simulation view, hides MuJoCo side panels and rotates the scene by 90 degrees
- arranges windows with MuJoCo at the bottom and webcam at the top-right corner
- starts `dora up`, runs `dora build <selected-demo> --uv`, and then `dora run <selected-demo> --uv`

Non-interactive example:

`powershell -ExecutionPolicy Bypass -File .\install_windows_real_demo.ps1 -NonInteractive -DemoFile dataflow_tracking_real.yml -CameraIndex 1 -ComPort COM4`


## Hand Setup

![Motors naming](docs/finger.png "Motors naming for each finger")

![Fingers naming](docs/r_hand.png "Fingers naming for each hand")

Be sure to adapt the configuration file [r_hand.toml](AHControl/config/r_hand.toml) for your particular hand.
You can use the software tools located in [AHControl](AHControl).


## Details

- [AHControl](AHControl) contains a dora-rs node to control the motors, along with some useful tools to configure them.
- [AHSimulation](AHSimulation) contains a dora-rs node to simulate the hand and get the inverse kinematics.
- [HandTracking](HandTracking) contains a dora-rs node to track hands from a webcam and use it as target to control AH!.

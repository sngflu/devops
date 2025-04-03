# Project Setup Guide

Thank you for your interest in this project! Here's a step-by-step guide on how to set up and run this project on your local machine.

## Prerequisites

Before you start, ensure you have the following software installed on your system:

1. **Python (version 3.9 or later)** - To check if Python is already installed, run python --version or python3 --version in your terminal.

2. **pip (version 19.0 or later)** - Python's package installer. It comes bundled with Python. To check if pip is installed, run pip --version or pip3 --version in your terminal.

3. **Node.js (version 14 or later)** - To check if Node.js is already installed, run `node -v` in your terminal.

4. **npm (version 6 or later)** - This comes bundled with Node.js. To check if npm is installed, run `npm -v` in your terminal.

5. **A modern web browser** - This project has been tested on the latest versions of Chrome, Firefox, Safari etc.

## Getting Started

Follow these steps to get the project up and running:

1. **Clone the repository** - You can do this by running the following command in your terminal:

   ```
   git clone https://github.com/sngflu/devops.git
   ```

2. **Navigate to the project directory** - Use the `cd` command to navigate into the project directory:

   ```
   cd devops
   ```

3. **Install dependencies** - Run the following command (frontend directory) to install all the dependencies required for the project:

   ```
   npm install
   ```

4. **Install requirements** - Run the following command (backend directory) to install all the dependencies required for the project:

   ```
   pip install -r requirements.txt
   ```

5. **Start the development server** - Run the following command (root directory) to start the development server:

   ```
   npm start
   ```

   The project should now be running at `http://localhost:5173`.

## Troubleshooting

If you encounter any issues while setting up the project, please check the following:

- Ensure that you have the correct versions of Node.js and npm installed.
- Make sure you've run `npm install` and `pip install -r requirements.txt` in the correct directories.
- Check the console for any error messages, which could give clues about what's going wrong.

If you're still having trouble, feel free to open an issue in the repository, and I'll do my best to help you out.

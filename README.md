# AI Foundry Data Agents

Sample Agents that demonstrate using Azure AI Foundry to host agents that are integrated with M365 Copilot as well as Teams. Users are able to interact with Fabric Data Agents and Databricks Genie instances using natural language queries. User identity is passed through from teams to the target enviroment to maintain user-based access control end-to-end.

## Local Environment Setup

Ensure you have the following installed in your local environment:

* [Python Language Support for VS Code](https://marketplace.visualstudio.com/items/?itemName=ms-python.python) extension installed and running.

* The most recent version of [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) is installed and working.

This repo assumes an environment running Ubuntu 24 LTS running on Windows 11 via Windows Subsystem for Linux with Python 3.12 or higher installed:

```bash
sudo apt install python
sudo apt install python3-pip
sudo apt install python-is-python3
sudo apt install python3.12-venv
```

Next, create a Python virtual environment at the root project folder:

```bash
python -m venv .venv
source .venv/bin/activate
```

Next, use the `requirements.txt` file to install the Python packages:

```bash
pip install -r requirements.txt

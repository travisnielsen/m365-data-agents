# AI Foundry Data Agents

Sample Agents that demonstrate using Azure AI Foundry to host agents that are integrated with M365 Copilot as well as Teams. Users are able to interact with Fabric Data Agents and Databricks Genie instances using natural language queries. User identity is passed through from teams to the target enviroment to maintain user-based access control end-to-end.

## Local Environment Setup

This repo assumes an environment running Ubuntu 24 LTS running on Windows 11 via Windows Subsystem for Linux (WSLv2) with Python 3.12 or higher installed:

```bash
sudo apt install python
sudo apt install python3-pip
sudo apt install python-is-python3
sudo apt install python3.12-venv
```
Create a Python virtual environment at the root project folder:

```bash
python -m venv .venv
source .venv/bin/activate
```

Use the `requirements.txt` file to install the Python packages:

```bash
pip install -r requirements.txt
```

Next, ensure you have the following developer tools installed:

* [Python Language Support for VS Code](https://marketplace.visualstudio.com/items/?itemName=ms-python.python)

* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

* [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu?view=powershell-7.5) and the [PowerShell Extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode.PowerShell)

* [Azure PowerShell module](https://learn.microsoft.com/en-us/powershell/azure/install-azps-linux?view=azps-14.3.0)

* [Azure Developer CLI (AZD)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux)

* Docker Desktop

## Deploy Infrastructure

### App Registration

This application requires an App Registration in your Entra ID tenant. Launch PowerShell (`pwsh`) from your terminal and naviagate to the project root directory. Run the following commands:

```powershell
Connect-AzAccount
./scripts/Create-AppRegistration.ps1
```

> ❗ **Important:** Be sure to copy the output from the script and save all the inforamtion. It will be needed in upcoming steps.

### Create Entra ID group

TBD

### Initialize the project

Open a bash terminal and navigate to the project root directory. Run the following command to initizlize the Azure Developer CLI:

`azd init`

In VS Code, open the **.env** file located within the **.azure** directory, which was created automatically in the previous step. Use the output from the app registration script that was run previously to update the file:

```dotenv
AZURE_ENV_NAME=[your_env_name]
AZURE_LOCATION=[your_azure_region]
AZURE_BOT_SERVICE_APP_ID=[your_app_registration_appid]
AZURE_BOT_SERVICE_APP_URI=[your_app_registration_uri]
AZURE_BOT_SERVICE_APP_API_SCOPE=[your_app_registration_api_scope]
AZURE_BOT_SERVICE_APP_CLIENT_SECRET=[your_app_registration_client_secret]
ENTRA_GROUP_OBJECT_ID=[your_entra_id_group_object_id]
```

### Provision Azure infrastructure

Ensure Docker is running in your local environment and use the following commands to deploy the Azure environment:

```bash
azd auth login
azd provision
```

# AI Foundry Data Agents

Sample Agents that demonstrate using Azure AI Foundry to host agents that are integrated with M365 Copilot as well as Teams. Users are able to interact with Fabric Data Agents and Databricks Genie instances using natural language queries. User identity is passed through from teams to the target enviroment to maintain user-based access control end-to-end. This sample is based on the [ADB-Teams Sample App](https://github.com/Azure-Samples/AI-Foundry-Connections/blob/main/src/samples/adb_aifoundry_teams/README.md)

> ❗IMPORTANT: This is a sample application to be used for demo purposes only. It is not intended for producution workloads.

## Local Environment Setup

This repo assumes an environment running Ubuntu 24 LTS running on Windows 11 via Windows Subsystem for Linux (WSLv2) with Python 3.12 or higher installed:

```bash
sudo apt install python
sudo apt install python3-pip
sudo apt install python-is-python3
sudo apt install python3.12-venv
```

Next, ensure you have the following developer tools installed:

* [Python Language Support for VS Code](https://marketplace.visualstudio.com/items/?itemName=ms-python.python)

* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)

* [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu?view=powershell-7.5) and the [PowerShell Extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode.PowerShell)

* [Azure PowerShell module](https://learn.microsoft.com/en-us/powershell/azure/install-azps-linux?view=azps-14.3.0)

* [Azure Developer CLI (AZD)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux)

* [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)

* [Dev Tunnels CLI](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started?tabs=linux)

## Deploy Infrastructure

### App Registration

This application requires an App Registration in your Entra ID tenant. Launch PowerShell (`pwsh`) from your terminal and naviagate to the project root directory. Run the following commands:

```powershell
Connect-AzAccount
./scripts/Create-AppRegistration.ps1
```

> ❗ **Important:** Be sure to copy the output from the script and save all the inforamtion. It will be needed in upcoming steps.

Finally, open the Azure Portal and navigate to **Microsoft Entra ID**. Go to **App Registraitons** and find the app named "M365 Data Agent" (all applications tab). Select the agent and then click **API permissions**. In the Configured Permissions section, select **Grant admin consent for [your_domain]**".

### Create Entra ID group

The application can generate images (charts and graphs) based on user prompts. These images are stored in a blob storage account. To provide read/write access to these images for display in Teams, an Entra ID group is used. You can create the group by running: [Create-EntraIdGroup.ps1](/scripts/Create-EntraIdGroup.ps1). Be sure to save the group object ID that is output by the script as it will be needed later for the infrastructure setup.

### Create Databricks workspace and Genie room

This sample currently assumes you have an existing Databricks workspace with Genie configured. Your test users must have read access to this environment.

### Configure Azure AI Foundry project

This sample currently assumes you have an existing AI Foundry project. For this sample application, three steps need to be taken:

1. From within your AI Foundry workspace, create a new Databricks Genie connection by navigating to **Management Center** > **Connected Resources**. Create a new **Azure Databricks** connection and follow the setup steps. Document the connection name when finished.
2. Document the **AI Foundry project endpoint**, which can be found in the **Overview** section of the project workspace.
3. Open the Azure Portal and navigate to your AI Foundry resource. Select the **Access control (IAM)** section and grant the App Registration **Azure AI Project Manager** permissions. This is necessary to allow the agent code to view informaiton about the Genie connection and create/use the agent instance hosted in AI Foundry.

> NOTE: We plan to automate these setup steps as part of the environment setup. We will also be looking into limiting the permissions granted to the agent code in a future update.

### Initialize the application environment

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
AZURE_BOT_SERVICE_OAUTH_CONNECTION_NAME="OauthBotAppConnection"
ENTRA_GROUP_OBJECT_ID=[your_entra_id_group_object_id]
```

### Provision Azure infrastructure

Ensure Docker is running in your local environment and use the following commands to deploy the Azure environment:

```bash
azd auth login
azd provision
```

## Publish the application to Teams

Update the values with square braces in the provided [manifest.json](/manifest/manifest.json) to match your environment. Be sure to use the values provided by the app registration script (above). Next, create a .zip file that contains the manifest.json, color.jpg, and outline.jpg files.

Upload the app to Teams by accessing the [Microsoft Teams Admin Center](https://admin.teams.microsoft.com/policies/manage-apps) and select **Actions** > **Upload new app**.

## Run locally

Create a Python virtual environment at the root project folder:

```bash
python -m venv .venv
source .venv/bin/activate
```

Use the `requirements.txt` file to install the Python packages:

```bash
pip install -r requirements.txt
```

Navigate to the [src](/src/) directory and create a new file named **.env**. Copy the contents from [env.sample](/src/env.sample) into this file and update the values to match your environment.

Create and host a local dev tunnel using the following command:

```bash
devtunnel user login -d
devtunnel create genie-agent-tunnel -a
devtunnel port create -p 3978 genie-agent-tunnel
devtunnel host genie-agent-tunnel
```

Go to the Azure portal and navigate to the Bot Service created earlier. Go to the **Configuration** pane and document the current value for **Messaging endpoint**. Next, replace it with the the dev tunnel URL provided in the CLI. Example: `https://ab0x1141-3978.use.devtunnels.ms/api/message`. Be sure to include the `/api/messages` path at the end. Click **Apply** when done.

## Deploy to Azure

Ensure Docker Desktop is running in your environment and use the `azd deploy` command to build the contianer image and push to the Azure Container Apps instance.

> NOTE: If you had previously been testing with Dev Tunnels, be sure to update your Azure Bot Service with the URL of your Container App.

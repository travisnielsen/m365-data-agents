@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}

param dataAgentsExists bool

@description('Object ID of the Entra ID group that end-users are members of. This group is granted Storage Blob Contributor access.')
param entraGroupObjectId string

@description('Id of the user or app to assign application roles')
param principalId string

@description('Principal type of user or app')
param principalType string

@description('The App ID of the bot service')
param botServiceAppId string

@description('The API scope for the bot service to access the app')
param botServiceAppApiScope string

@description('The Application ID URI for the bot service app registration')
param botServiceAppUri string

@secure()
param botServiceAppClientSecret string

// @description('The endpoint for the bot service to forward messages to: example: https://your-agent-endpoint.azurewebsites.net/api/messages')
// param agentMessagingEndpoint string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}
// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
    roleAssignments:[
      {
        principalId: dataAgentsIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
    ]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module dataAgentsIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'dataAgentsidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}dataAgents-${resourceToken}'
    location: location
  }
}
module dataAgentsFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'dataAgents-fetch-image'
  params: {
    exists: dataAgentsExists
    name: 'data-agents'
  }
}

module dataAgents 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'dataAgents'
  params: {
    name: 'data-agents'
    ingressTargetPort: 80
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  [
      ]
    }
    containers: [
      {
        image: dataAgentsFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: dataAgentsIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '80'
          }
        ]
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [dataAgentsIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: dataAgentsIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'data-agents' })
  }
}

// Storage account and container
module storage 'br/public:avm/res/storage/storage-account:0.26.2' = {
  name: 'storage'
  params: {
    name: '${abbrs.storageStorageAccounts}${resourceToken}'
    location: location
    tags: tags
    allowBlobPublicAccess: true
    publicNetworkAccess: 'Enabled'
  }
}

module container 'br/public:avm/res/storage/storage-account/blob-service/container:0.2.0' = {
  name: 'container'
  params: {
    name: 'images'
    storageAccountName: storage.outputs.name
  }
}

// grant the teams users group blob contributor access to the storage account
resource blobContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceToken, 'blobContributor')
  properties: {
    principalId: entraGroupObjectId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalType: 'Group'
  }
}

// create azure bot service
module botService 'modules/botservice.bicep' = {
  name: 'botService'
  params: {
    tags: tags
    name: 'm365bot-${resourceToken}'
    displayName: 'M365 Data Agent Bot'
    appId: botServiceAppId
    appUri: botServiceAppUri
    appApiScope: botServiceAppApiScope
    appClientSecret: botServiceAppClientSecret
    tenantId: tenant().tenantId
    endpoint: 'https://${dataAgents.outputs.fqdn}/api/messages'
  }
}

output AZURE_STOREAGE_ACCOUNT_NAME string = storage.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_DATA_AGENTS_ID string = dataAgents.outputs.resourceId

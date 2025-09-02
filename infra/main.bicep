targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

param dataAgentsExists bool

@description('Object ID of the Entra ID group that end-users are members of. This group is granted Storage Blob Contributor access.')
param entraGroupObjectId string

@description('Id of the user or app to assign application roles')
param principalId string

@description('Principal type of user or app')
param principalType string

@description('The application ID of the Entra ID registration to be used for the Bot Service')
param botServiceAppId string

@description('The API scope for the bot service to access the app')
param botServiceAppApiScope string

@description('The Application ID URI for the bot service app registration')
param botServiceAppUri string

@description('The client secret for the bot service app registration')
@secure()
param botServiceAppClientSecret string

// Tags that should be applied to all resources.
// 
// Note that 'azd-service-name' tags should be applied separately to service host resources.
// Example usage:
//   tags: union(tags, { 'azd-service-name': <service name in azure.yaml> })
var tags = {
  'azd-env-name': environmentName
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  scope: rg
  name: 'resources'
  params: {
    location: location
    tags: tags
    principalId: principalId
    principalType: principalType
    dataAgentsExists: dataAgentsExists
    botServiceAppId: botServiceAppId
    botServiceAppUri: botServiceAppUri
    botServiceAppApiScope: botServiceAppApiScope
    botServiceAppClientSecret: botServiceAppClientSecret
    entraGroupObjectId: entraGroupObjectId
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_RESOURCE_DATA_AGENTS_ID string = resources.outputs.AZURE_RESOURCE_DATA_AGENTS_ID

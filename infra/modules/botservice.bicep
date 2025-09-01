param location string
param tags object
param displayName string
param appId string
param tenantId string

@description('The endpoint for the bot service to forward messages to: example: https://your-agent-endpoint.azurewebsites.net/api/messages')
param endpoint string

resource botService 'Microsoft.BotService/botServices@2021-03-01' = {
  name: 'botService'
  location: location
  tags: tags
  sku: {
    name: 'S1'
  }
  properties: {
    displayName: displayName
    endpoint: endpoint
    msaAppId: appId
    msaAppTenantId: tenantId
    msaAppType: 'SingleTenant'
  }
}

param tags object
param name string
param displayName string
param appId string
param appUri string
param appApiScope string
@secure()
param appClientSecret string
param tenantId string


@description('The endpoint for the bot service to forward messages to: example: https://your-agent-endpoint.azurewebsites.net/api/messages')
param endpoint string

resource botService 'Microsoft.BotService/botServices@2023-09-15-preview' = {
  name: name
  location: 'global'
  kind: 'azurebot'
  tags: tags
  sku: {
    name: 'S1'
  }
  properties: {
    displayName: displayName
    endpoint: endpoint
    msaAppId: appId
    msaAppTenantId: tenantId
    schemaTransformationVersion: '1.3'
    msaAppType: 'SingleTenant'
  }
}


resource botServiceChannelSettings 'Microsoft.BotService/botServices/channels@2023-09-15-preview' = {
  name: 'MsTeamsChannel'
  parent: botService
  location: 'global'
  properties:{
      channelName: 'MsTeamsChannel'
      properties:{
          isEnabled: true
          acceptedTerms: true
      }
  }
}

resource botServiceConnections 'Microsoft.BotService/botServices/connections@2023-09-15-preview' = {
  name: 'OauthBotAppConnection'
  parent: botService
  location: 'global'
  properties: {
    name: 'M365 Data Agent App Connection'
    clientId: appId
    clientSecret: appClientSecret
    scopes: appApiScope
    serviceProviderDisplayName: 'Azure Active Directory v2'
    serviceProviderId: '30dd229c-58e3-4a48-bdfd-91ec48eb906c'
    parameters: [
      {
        key: 'tenantId'
        value: tenantId
      }
      {
        key: 'tokenExchangeUrl'
        value: appUri
      }
    ]
  }
}

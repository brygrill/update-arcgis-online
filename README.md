# Update ArcGIS Online Data
Extract fresh data and push to ArcGIS Online. Enter credentials and select features to update through Catalog Toolbox tool. 

Wired up with [this script](https://github.com/arcpy/update-hosted-feature-service) from Esri. See their repo for configuration. ```TalktoAGOL``` module executes the Esri script to interact with ArcGIS Online.

To-do:
- Make ```renameFeatures``` function work properly
- Tighten up logic
- Add more data
- Configure to run weekly 

#-------------------------------------------------------------------------------
# Name:        Update AGOL
# Purpose:     Update AGOL Feature Classes
#
# Author:      GrillB
#
# Created:     02/02/2016
# Copyright:   (c) GrillB 2016
# Credits:     https://github.com/arcpy/update-hosted-feature-service
#-------------------------------------------------------------------------------

""" Prep """
import os, arcpy, ConfigParser, TalkToAGOL
from arcpy import env

# Overwrite Output
arcpy.env.overwriteOutput=True

# Set Workspace
root = r"path\to\project\root"
outputGDB = os.path.join(root, "YourGDB.gdb")
env.workspace = outputGDB

# AGOL Credentials
inputUserName = arcpy.GetParameterAsText(0)
inputPassword = arcpy.GetParameterAsText(1)

# User selected services to update
selectedServices = arcpy.GetParameterAsText(2)

#Post Owner Name?
postOwnerName = arcpy.GetParameterAsText(3)

# Data Pathes
nq_addPts = r"\\nq-cluster1\share-appl\GISData\countywide\address.shp"
SDE_parcel = r"path\to\data\parcel_poly"
SDE_uga = r"path\to\data\Uga_poly"
SDE_zoning = r"path\to\data\Zoning"
SDE_cemetery = r"path\to\data\Cemetery"
SDE_parks = r"path\to\data\parks"
SDE_trails = r"path\to\data\Trails"
SDE_ASA = r"path\to\data\Agsecurity"
SDE_Ease = r"path\to\data\AgEasements"

# Service Location Variable and Settings.ini Name
serviceDictionary = {"AddressPts" : nq_addPts, "Parcels" : SDE_parcel, "UGA" : SDE_uga, "Zoning" : SDE_zoning, "Cemetery" : SDE_cemetery,
    "Parks" : SDE_parks, "Trails" : SDE_trails, "AgSecurity" : SDE_ASA, "AgEasements" : SDE_Ease}

# List of Feature Services to be extracted
serviceList = selectedServices.split(';')
dataList = []

""" Functions To Call """
# Clean Up Gdb
def cleanGDB():
    arcpy.env.workspace = outputGDB
    featureclasses = arcpy.ListFeatureClasses()
    for feature in featureclasses:
        if feature in serviceList:
            arcpy.Delete_management(feature)

# Rename Features
def renameFeature(oldName, newName):
    arcpy.env.workspace = outputGDB
    arcpy.Rename_management(oldName, oldName+"TEMP")
    arcpy.Rename_management(oldName+"TEMP", newName)

# Add and calc field function
def addCalcField(featureName, fieldName, fieldType, fieldLength, fieldCalc, codeBlock):
    arcpy.AddField_management(featureName, fieldName, fieldType, "", "", fieldLength, "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.CalculateField_management(featureName, fieldName, fieldCalc, "PYTHON_9.3", codeBlock)

# Transform Sale Date to MMDDYYYY
def modifyParcelData():
    dateCode = """def calcSale(DATE2):
    if (DATE2 == 0):
        return 1/1/1900
    else:
        return DATE2[4:6] + "/" + DATE2[6:8] + "/" + DATE2[0:4]"""
    addCalcField("parcels", "SALEDATE", "DATE", "", "calcSale(!SALE_DATE!)", dateCode)

# Make Parcels with owner name
def processParcelDetails():
    arcpy.CopyFeatures_management("parcels", "parcels_Name")

    assessmentURL = '"http://lcapp1.co.lancaster.pa.us/aoweb/ParcelDetails.aspx?ParcelID=" + !ACCOUNT! + "|&searchType=propID&propID=" + !ACCOUNT!'
    addCalcField("parcels_Name", "ASSESSLINK", "TEXT", "120", assessmentURL, "")

""" Script Functions """
# Extract the Data
def extractFeatureServices():
    # Prep GDB
    if not arcpy.Exists(outputGDB):
        arcpy.CreateFileGDB_management(root, "YourGDB.gdb")

    # Delete feature class that will be extracted
    cleanGDB()

    # Build the list of feature classes to extract
    for feature in serviceList:
        dataList.append(serviceDictionary[feature])

    # Export from SDE to local GDB
    arcpy.FeatureClassToGeodatabase_conversion(dataList, outputGDB)

    # Features to Proper Case
    # ********** This part doesnt work **************
    if "Parks" in serviceList:
        renameFeature("parks", "Parks")
    if "AddressPoints" in serviceList:
        renameFeature("address", "AddressPts")
    if "AgSecurity" in serviceList:
        renameFeature("Agsecurity", "AgSecurity")
    if "UGA" in serviceList:
        renameFeature("Uga_poly", "UGA")

    # Rename parcel_poly to parcels and add Parcel_Name
    if "Parcels" in serviceList:
        renameFeature("parcel_poly", "Parcels")
        modifyParcelData()
        if postOwnerName == "Yes":
            processParcelDetails()

# Post to AGOL
def postIt():
    # List of Map Service Settings
    settingsFile = r"path\to\settings.ini"

    # Read Settings for each Map Service
    if os.path.isfile(settingsFile):
        config = ConfigParser.ConfigParser()
        config.read(settingsFile)
    else:
        print("INI file not found. \nMake sure a valid 'settings.ini' file exists in the same directory as this script.")
        arcpy.AddMessage("INI file not found. \nMake sure a valid 'settings.ini' file exists in the same directory as this script.")
        sys.exit()

    # Loop through selected services and pass info to Esri update script
    for item in serviceList:
        MXD = config.get(item, 'MXDNAME')
        serviceName = config.get(item, 'SERVICENAME')
        tags = config.get(item, 'TAGS')
        desc = config.get(item, 'DESCRIPTION')
        groups = config.get(item, 'GROUPS')

        # launch Esri script to post Feature Service
        TalkToAGOL.overwrite(inputUserName, inputPassword, MXD, serviceName, tags, desc, groups)
        arcpy.AddMessage(item + " Posted to AGOL")

""" Run It """
def main():
    extractFeatureServices()
    postIt()

if __name__ == '__main__':
    main()

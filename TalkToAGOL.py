# This is a forked version of an Esri script. Link to Esri repo in README
 
# Import system modules
import urllib, urllib2, json
import sys, os

import arcpy
import shutil
import ConfigParser
from xml.etree import ElementTree as ET

#Ensure reqests module is there, needed to push update to AGOL
destination = r"C:\Python27\ArcGIS10.3\Lib\site-packages\requests"
copyfrom = r"S:\GIS\GISSoftware\ArcGIS10_2_1\Python\requests-master\requests"

if os.path.exists(destination):
    pass
else:
    shutil.copytree(copyfrom, destination, symlinks=False, ignore=None)
    print "Copied Request module to %s" % (destination)

import requests

def overwrite(inputusername, inputpassword, MXD_over, serviceName_over, tags_over, desc_over, groups_over):
    class AGOLHandler(object):

        def __init__(self, username, password, serviceName):
            self.username = username
            self.password = password
            self.serviceName = serviceName
            self.token, self.http = self.getToken(username, password)
            self.itemID = self.findItem("Feature Service")
            self.SDitemID = self.findItem("Service Definition")

        def getToken(self, username, password, exp=60):

            referer = "http://www.arcgis.com/"
            query_dict = {'username': username,
                          'password': password,
                          'expiration': str(exp),
                          'client': 'referer',
                          'referer': referer,
                          'f': 'json'}

            query_string = urllib.urlencode(query_dict)
            url = "https://www.arcgis.com/sharing/rest/generateToken"

            token = json.loads(urllib.urlopen(url + "?f=json", query_string).read())

            if "token" not in token:
                print token['error']
                sys.exit()
            else:
                httpPrefix = "http://www.arcgis.com/sharing/rest"
                if token['ssl'] == True:
                    httpPrefix = "https://www.arcgis.com/sharing/rest"

                return token['token'], httpPrefix

        def findItem(self, findType):
        #
        # Find the itemID of whats being updated
        #
            searchURL = self.http + "/search"

            query_dict = {'f': 'json',
                        'token': self.token,
                        'q': "title:\""+ self.serviceName + "\"AND owner:\"" + self.username + "\" AND type:\"" + findType + "\""}

            jsonResponse = sendAGOLReq(searchURL, query_dict)

            if jsonResponse['total'] == 0:
                print "\nCould not find a service to update. Check the service name in the settings.ini"
                sys.exit()
            else:
                print("found {} : {}").format(findType, jsonResponse['results'][0]["id"])

            return jsonResponse['results'][0]["id"]


    def urlopen(url, data=None):
        # monkey-patch URLOPEN
        referer = "http://www.arcgis.com/"
        req = urllib2.Request(url)
        req.add_header('Referer', referer)

        if data:
            response = urllib2.urlopen(req, data)
        else:
            response = urllib2.urlopen(req)

        return response


    def makeSD(MXD, serviceName, tempDir, outputSD, maxRecords):
        #
        # create a draft SD and modify the properties to overwrite an existing FS
        #

        arcpy.env.overwriteOutput = True
        # All paths are built by joining names to the tempPath
        SDdraft = os.path.join(tempDir, "tempdraft.sddraft")
        newSDdraft = os.path.join(tempDir, "updatedDraft.sddraft")

        arcpy.mapping.CreateMapSDDraft(MXD, SDdraft, serviceName, "MY_HOSTED_SERVICES")

        # Read the contents of the original SDDraft into an xml parser
        doc = ET.parse(SDdraft)

        root_elem = doc.getroot()
        if root_elem.tag != "SVCManifest":
            raise ValueError("Root tag is incorrect. Is {} a .sddraft file?".format(SDDraft))

        # Change service type from map service to feature service
        for config in doc.findall("./Configurations/SVCConfiguration/TypeName"):
            if config.text == "MapServer":
                config.text = "FeatureServer"

        #Turn off caching
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/" +
                                    "ConfigurationProperties/PropertyArray/" +
                                    "PropertySetProperty"):
            if prop.find("Key").text == 'isCached':
                prop.find("Value").text = "false"
            if prop.find("Key").text == 'maxRecordCount':
                prop.find("Value").text = maxRecords

        # Turn on feature access capabilities
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/Info/PropertyArray/PropertySetProperty"):
            if prop.find("Key").text == 'WebCapabilities':
##                prop.find("Value").text = "Query,Create,Update,Delete,Uploads,Editing"
                prop.find("Value").text = "Query"

        # Add the namespaces which get stripped, back into the .SD
        root_elem.attrib["xmlns:typens"] = 'http://www.esri.com/schemas/ArcGIS/10.1'
        root_elem.attrib["xmlns:xs"] ='http://www.w3.org/2001/XMLSchema'

        # Write the new draft to disk
        with open(newSDdraft, 'w') as f:
            doc.write(f, 'utf-8')

        # Analyze the service
        analysis = arcpy.mapping.AnalyzeForSD(newSDdraft)

        if analysis['errors'] == {}:
            # Stage the service
            arcpy.StageService_server(newSDdraft, outputSD)
            print "Created {}".format(outputSD)

        else:
            # If the sddraft analysis contained errors, display them and quit.
            print analysis['errors']
            sys.exit()


    def upload(fileName, tags, description):
        #
        # Overwrite the SD on AGOL with the new SD.
        # This method uses 3rd party module: requests
        #

        updateURL = agol.http+'/content/users/{}/items/{}/update'.format(agol.username, agol.SDitemID)

        filesUp = {"file": open(fileName, 'rb')}

        url = updateURL + "?f=json&token="+agol.token+ \
            "&filename="+fileName+ \
            "&type=Service Definition"\
            "&title="+agol.serviceName+ \
            "&tags="+tags+\
            "&description="+description

        response = requests.post(url, files=filesUp);
        itemPartJSON = json.loads(response.text)

        if "success" in itemPartJSON:
            itemPartID = itemPartJSON['id']
            print("updated SD:   {}").format(itemPartID)
            return True
        else:
            print "\n.sd file not uploaded. Check the errors and try again.\n"
            print itemPartJSON
            sys.exit()


    def publish():
        #
        # Publish the existing SD on AGOL (it will be turned into a Feature Service)
        #

        publishURL = agol.http+'/content/users/{}/publish'.format(agol.username)

        query_dict = {'itemID': agol.SDitemID,
                  'filetype': 'serviceDefinition',
                  'f': 'json',
                  'token': agol.token}

        jsonResponse = sendAGOLReq(publishURL, query_dict)

        print("successfully updated...{}...").format(jsonResponse['services'])

        return jsonResponse['services'][0]['serviceItemId']


    def deleteExisting():
        #
        # Delete the item from AGOL
        #

        deleteURL = agol.http+'/content/users/{}/items/{}/delete'.format(agol.username, agol.itemID)

        query_dict = {'f': 'json',
                      'token': agol.token}

        jsonResponse = sendAGOLReq(deleteURL, query_dict)

        print("successfully deleted...{}...").format(jsonResponse['itemId'])



    def enableSharing(newItemID, everyone, orgs, groups):
        #
        # Share an item with everyone, the organization and/or groups
        #
        shareURL = agol.http+'/content/users/{}/items/{}/share'.format(agol.username, newItemID)

        if groups == None:
            groups = ''

        query_dict = {'f': 'json',
                      'everyone' : everyone,
                      'org' : orgs,
                      'groups' : groups,
                      'token': agol.token}

        jsonResponse = sendAGOLReq(shareURL, query_dict)

        print("successfully shared...{}...").format(jsonResponse['itemId'])



    def sendAGOLReq(URL, query_dict):
        #
        # Helper function which takes a URL and a dictionary and sends the request
        #

        query_string = urllib.urlencode(query_dict)

        jsonResponse = urllib.urlopen(URL, urllib.urlencode(query_dict))
        jsonOuput = json.loads(jsonResponse.read())

        wordTest = ["success", "results", "services", "notSharedWith"]
        if any(word in jsonOuput for word in wordTest):
            return jsonOuput
        else:
            print "\nfailed:"
            print jsonOuput
            sys.exit()

    #
    # start
    #

    print "Starting Feature Service publish process"
    arcpy.AddMessage("Starting Feature Service publish process")


    localPath = sys.path[0]

    # FS values
    MXD = "S:\GIS\ArcGIS_Online\Services_MXDs\%s.mxd" % (MXD_over)
    serviceName = serviceName_over
    tags = tags_over
    #MXD = "S:\GIS\GISData\ArcGIS_Online\Services\AgSecurityAreas.mxd"
    #serviceName = "AgSecurityAreas"
    #tags = "Ag, APB, App, ASA, Farms, LFT, Easement, Ag Security Areas"
    description = desc_over
    maxRecords = "1000"

    # Share FS to: everyone, org, groups
    shared = "True"
    everyone = "true"
    orgs = "true"
    groups = groups_over
    #groups = "None"  #Groups are by ID. Multiple groups comma separated


    # create a temp directory under the script
    tempDir = os.path.join(localPath, "tempDir")
    if not os.path.isdir(tempDir):
        os.mkdir(tempDir)
    finalSD = os.path.join(tempDir, serviceName + ".sd")

    #initialize AGOLHandler class
    agol = AGOLHandler(inputusername, inputpassword, serviceName)

    # Turn map document into .SD file for uploading
    makeSD(MXD, serviceName, tempDir, finalSD, maxRecords)

    # overwrite the existing .SD on arcgis.com

    if upload(finalSD, tags, description):

        # delete the existing service
        deleteExisting()

        # publish the sd which was just uploaded
        newItemID = publish()

        # share the item
        if shared:
            enableSharing(newItemID, everyone, orgs, groups)

    print "\n%s Finished.\n" % (serviceName_over)

    arcpy.Delete_management(tempDir)

if __name__ == '__main__':
    overwrite()

# ABX Action to send to email as part of ABX Flow: Ultimate Notifications
# Created by Guillermo Martinez and Dennis Gerolymatos 
# Version 1.4 - 22.12.2021

import json # API query responses to json.
import requests # query the API
import smtplib # send email
import sys # exit the script
import pytz # time zone
import ssl # SSL email
from email.mime.text import MIMEText # mime objects on Email
from email.mime.multipart import MIMEMultipart # emails with HTML content
from json2table import convert # diccionaries to html
from datetime import datetime #  current time

def handler(context, inputs):
    # VARIABLES

    global apiVersion; apiVersion="2021-07-15" # tested with version 2021-07-15
   
    # Creates a dictionary with all neccesary data from VRa API and context inputs
    depInfoAndRes=create_dictionary(inputs)
    
    # calls generate_html function to populate the HTML body
    html=generate_html(inputs,depInfoAndRes)
    
    # calls the function for sending the email.
    send_email(context,inputs,html,depInfoAndRes)

    outputs={}
    outputs['depInfoAndRes']=depInfoAndRes
    outputs['messageSubject']=depInfoAndRes['status']+" - Status of deployment "+depInfoAndRes["name"]+" by "+depInfoAndRes['proGrpContent']['platform_name']['const'] # Subject for the notification
    return outputs

# Gets inputs from the VRa API and the deployment context and build a Dictionary
def create_dictionary(inputs):
    # VARIABLES
    global apiVersion
    orgId=inputs["orgId"] # gets organization ID from the inputs
    depInfoAndRes={}# Declaring the main dictionary
    bearer=inputs['bearerToken']  #Before querying the API, a bearer token needs to be obtained.
    projectId=inputs["projectId"] # reads the project ID from the inputs
    deploymentId=inputs['deploymentId'] # deployment ID from the inputs
    userName=inputs["userName"] # username from the context inputs
    vraUrl=inputs["vra_fqdn"] # vRA url
    eventType=inputs["eventType"] if "eventType" in inputs else "EXPIRE_NOTIFICATION" # evenType from the context inputs
    eventTopicId=inputs["__metadata"]["eventTopicId"] # event topic ID from the context inputs

    
    # defining a common header for all the subsequent API queries.
    headers={"Accept":"application/json","Content-Type":"application/json", "Authorization":bearer}
    
    # test vRA API Connection
    print("Testing vRA API Connection...")
    apiAbout=requests.get('https://' + vraUrl + '/project-service/api/about?apiVersion='+apiVersion, data='', headers=headers, verify=False)
    if apiAbout.status_code==200:
        print("Connection to vRA tested succesfully...")
    else:
        print('[?] Unexpected Error: [HTTP {0}]: Content: {1}'.format(apiAbout.status_code, apiAbout.content))
        sys.exit("Error: Connection to vRA API was not made succesfully")

    # Getting inputs from property group by querying the API
    print('Querying API to get property group name...')
    projectInfoJson=requests.get('https://' + vraUrl + '/project-service/api/projects/'+projectId+'?apiVersion='+apiVersion , data='', headers=headers, verify=False)
    propGrp=projectInfoJson.json()['properties']['propertyGroup']
    print('Getting inputs from property group...')
    propGrpInpJson=requests.get('https://' + vraUrl + '/properties/api/property-groups/?apiVersion='+apiVersion+'&name=' + propGrp , data='', headers=headers, verify=False)
    proGrpInp=propGrpInpJson.json()

    # Adding all property group variables to the dictionary
    depInfoAndRes['proGrpContent']=proGrpInp["content"][0]['properties']

    # Time Zone settings #
    localTZ=pytz.timezone(depInfoAndRes['proGrpContent']['timeZone']['const'])

    # Discovering Deployment info and resources by querying the API
    print('Discovering deployment info and resources...')
    deploymentInfoJson=requests.get('https://' + vraUrl + '/deployment/api/deployments/' + deploymentId + '?apiVersion='+apiVersion+'&deleted=true&expand=project&expand=resources', data='', headers=headers, verify=False)
    depInfo=deploymentInfoJson.json()
    # Date and Time Formating and Time Zone Convertion
    createdAtConverted=depInfo['createdAt'].replace("T"," ").replace("Z","").split(".")
    createdAtConverted=datetime.strptime(createdAtConverted[0],"%Y-%m-%d %H:%M:%S").astimezone(localTZ).strftime("%Y-%m-%d %H:%M:%S")
    lastUpdatedConverted=depInfo['lastUpdatedAt'].replace("T"," ").replace("Z","").split(".")
    lastUpdatedConverted=datetime.strptime(lastUpdatedConverted[0],"%Y-%m-%d %H:%M:%S").astimezone(localTZ).strftime("%Y-%m-%d %H:%M:%S")
    if "leaseExpireAt" in depInfo:
        leaseExpireConverted=depInfo['leaseExpireAt'].replace("T"," ").replace("Z","").split(".")
        leaseExpireConverted=datetime.strptime(leaseExpireConverted[0],"%Y-%m-%d %H:%M:%S").astimezone(localTZ).strftime("%Y-%m-%d %H:%M:%S")
    else:
        leaseExpireConverted=""
    
    # Populate main dictionary with more data
    depInfoAndRes["name"]=depInfo['name'] if "name" in depInfo else " "
    depInfoAndRes["description"]=depInfo['description'] if "description" in depInfo else " "
    depInfoAndRes["id"]=depInfo['id'] if "id" in depInfo else " "
    depInfoAndRes["status"]=depInfo['status'] if "status" in depInfo else " "
    depInfoAndRes["createdAt"]=createdAtConverted
    depInfoAndRes["leaseExpireAt"]=leaseExpireConverted
    depInfoAndRes["createdBy"]=depInfo['createdBy'] if "createdBy" in depInfo else " "
    depInfoAndRes["ownedBy"]=depInfo['ownedBy'] if "ownedBy" in depInfo else " "
    depInfoAndRes["lastUpdatedAt"]=lastUpdatedConverted
    depInfoAndRes["projectName"]=depInfo['project']['name'] if "name" in depInfo['project'] else " "
    depInfoAndRes["lastUpdatedBy"]=depInfo['lastUpdatedBy'] if "lastUpdatedBy" in depInfo else " "

    #Loop through all resources in the deployment and create a nested dictionary with the resources details.
    i=0
    resDetails={}
    depResources=depInfo["resources"]
    while i < len(depResources):
        # Date and Time Formating and Time Zone Convertion
        createdAtConverted=depResources[i]["createdAt"].replace("T"," ").replace("Z","").split(".") # date from the API, unrecognized characters are removed.
        createdAtConverted=datetime.strptime(createdAtConverted[0],"%Y-%m-%d %H:%M:%S").astimezone(localTZ).strftime("%Y-%m-%d %H:%M:%S") # date from the API is converted to time object and to local time zone
        resourceName=depResources[i]["name"] if depResources[i]["type"]=="Cloud.NSX.Network" else depResources[i]["properties"]["resourceName"]
        resDetails[resourceName]={
        "Name": resourceName,
        "Type": depResources[i]["type"],
        "State": depResources[i]["state"],
        "started At": createdAtConverted
        }
        #if resouce type is Cloud.vSphere.Machine, query the API for additional resource details.
        if depResources[i]["type"]=="Cloud.vSphere.Machine":
            resourceId=depResources[i]["id"]
            VMDetailsJson=requests.get('https://' + vraUrl + '/deployment/api/resources/' + resourceId + '?apiVersion='+apiVersion+'', data='', headers=headers, verify=False)
            VMDetails=VMDetailsJson.json()
            VMDetailsProperties=VMDetails["properties"]
            resDetails[resourceName]["IP Address"]=VMDetailsProperties["address"] if "address" in VMDetailsProperties else ""
            resDetails[resourceName]["CPU count"]= VMDetailsProperties["cpuCount"] if "cpuCount" in VMDetailsProperties else ""
            resDetails[resourceName]["Total Memory MB"]= VMDetailsProperties["totalMemoryMB"] if "totalMemoryMB" in VMDetailsProperties else ""
            resDetails[resourceName]["Operating System"]= VMDetailsProperties["softwareName"] if "softwareName" in VMDetailsProperties else ""
            #Loop through all disks and add them to the dictionary.
            if "disks" in VMDetailsProperties["storage"]:
                j=0
                while j < len(VMDetailsProperties["storage"]["disks"]):
                    resDetails[resourceName]["disk "+str(j)]={
                    "Name":VMDetailsProperties["storage"]["disks"][j]["name"],
                    "Type":VMDetailsProperties["storage"]["disks"][j]["type"],
                    "Capacity GB":VMDetailsProperties["storage"]["disks"][j]["capacityGb"]
                    }
                    j+=1
        i+=1
        
    #adds an aditional entry to the dictionary with the resource details.
    depInfoAndRes["Resources"]=resDetails
    
    # Getting details about the request and adding them to the dictionary.
    requestInfo=requests.get('https://' + vraUrl + '/deployment/api/requests/'+inputs["id"]+'?apiVersion='+apiVersion, data='', headers=headers, verify=False)
    requestInfoJson=requestInfo.json()
    
    # Checking if approval is required.
    if eventType=="CREATE_DEPLOYMENT" and eventTopicId=="deployment.request.pre":
        print("Checking if approval is required...")
        while int(requestInfoJson["completedTasks"]) < 4:
            if requestInfoJson["status"]=="APPROVAL_PENDING":
                depInfoAndRes['status']="APPROVAL_PENDING"
                print("Approval is required...")
                break
            requestInfo=requests.get('https://' + vraUrl + '/deployment/api/requests/'+inputs["id"]+'?apiVersion='+apiVersion, data='', headers=headers, verify=False)
            requestInfoJson=requestInfo.json()   
            
    depInfoAndRes['requestDetails']=requestInfoJson["details"] if (requestInfoJson["details"]!="")  else "No additional details."
    depInfoAndRes['requestStatus']=requestInfoJson["status"] if "status" in requestInfoJson else "No Status"
    
    
    # setting variables in case the lease has expired.
    if userName=="system-user" and inputs['actionName']=="Expire":
        userName=depInfoAndRes['createdBy']
        depInfoAndRes['status']="LEASE_EXPIRED"

    # Discovering Requestor's Email and First Name by querying the API
    print("Discovering Requestor's Email...")
    userId=inputs['userId'].split(":")[1]
    response_Email=requests.get('https://' + vraUrl + '/csp/gateway/am/api/users/' + userId + '/orgs/' + orgId + '/info?apiVersion='+apiVersion, data='', headers=headers, verify=False)
    depInfoAndRes['requestorEmail']=response_Email.json()['user']['email'] # gets the email from the user who launched the deployment.
    depInfoAndRes['requestorFirstName']=response_Email.json()['user']['firstName'] # gets the first name from the user who launched the deployment.
    
    return depInfoAndRes
    
# Format HTML body of the email.
def generate_html(inputs,depInfoAndRes):
    #VARIABLES
    global apiVersion
    localTZ=pytz.timezone(depInfoAndRes['proGrpContent']['timeZone']['const']) # Time Zone settings
    bearer=inputs['bearerToken']  #Before querying the API, a bearer token needs to be obtained.
    bulkRequestCount="1" # for expenses simulation
    deploymentId=inputs['deploymentId'] # deployment ID from the inputs
    vraUrl=inputs["vra_fqdn"] # vRA url
    eventType=inputs["eventType"] if "eventType" in inputs else "EXPIRE_NOTIFICATION" # evenType from the context inputs
    eventTopicId=inputs["__metadata"]["eventTopicId"] # event topic ID from the context inputs
    headers={"Accept":"application/json","Content-Type":"application/json", "Authorization":bearer} # defining a common header for all the subsequent API queries.
    logoWidth =depInfoAndRes['proGrpContent']['logo_company_width_pixels']['const'] if 'logo_company_width_pixels' in depInfoAndRes['proGrpContent'] else " "  # defines the width size of the logo in pixels.
    logoHeight=depInfoAndRes['proGrpContent']['logo_company_height_pixels']['const'] if 'logo_company_height_pixels' in depInfoAndRes['proGrpContent'] else " "   # defines the heights size of the logo in pixelso.
    logoCompany=depInfoAndRes['proGrpContent']['logo']['const'] if 'logo' in depInfoAndRes['proGrpContent'] else " "   # gets the string corresponding to the base64 encoded JPG logo.
    userNameFirstName=depInfoAndRes['requestorFirstName'] # Requestors First Name
    dateAndTime=datetime.now().astimezone(localTZ).strftime("%Y-%m-%d %H:%M:%S") # gets current date and time, applies a format and convert to local time zone
    build_direction="LEFT_TO_RIGHT" # Neccesary for the convert dictionary to HTML function

    # applies the same style to all tables, rows and cells on the HTML body in all Event Types
    htmlStyle = f'''                                                                                    
              <style>
          table {{
                width: 100%;
                border: 1px solid black;
                border-radius: 20px;
                }}

          td {{
                text-align: left;
                padding: 8px;
                border: 1px solid black;
                background-color: #F7F9F9;
                border-radius: 10px;
                 }}
                 
          th     {{
                text-align: left;
                padding: 8px;
                border: 1px solid black;
                background-color: #EBF5FB;
                border-radius: 10px;
                 }}
          tr {{
              background-color: #FDFEFE;
              }}
        .container {{
        width: {logoWidth}px;
        height: {logoHeight}px;
                }}
        img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
            }}
    </style style="width:100%">
    '''
    
    # uses the global variable logoCompany for adding the logo to the HTML body
    logo=f'''\
    <div class="container">
      <img src="data:image/png;base64, {logoCompany}" alt="Image" />
    </div>
    
    '''
    
    mailFooter=f'''\
    <table>
     <tr>
      <td>
       <a href="https://{vraUrl}/automation-ui/#/deployment-ui;ash=%2Fworkload%2Fdeployment%2F{deploymentId}">Click here to see your request</a>
      </td>
     </tr>
    </table>
    '''
    
    # write the HTML Template for each Event Type
    if eventType=="CREATE_DEPLOYMENT" and eventTopicId=="deployment.request.pre": # The deployment has just started
        if depInfoAndRes['status']=="APPROVAL_PENDING":
            mailHeader=f'''\
            <p>Your request for deployment <strong>{depInfoAndRes["name"]}</strong>
            is pending for approval.</p>
            <table>
            <tr>
                <td>
                <h2><strong>Deployment Information:</strong></h2>
                <ul>
                    <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
                    <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
                    <li> Deployment started at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
                    <li> Deployment status: <strong> {depInfoAndRes['status']}</strong></li>
                    <li> Deployment details: <strong> {depInfoAndRes['requestDetails']}</strong></li>
                    </ul>
                    </td>
                    </tr>
            </table>
            '''
        else:
            mailHeader=f'''\
            <p>Your request for deployment <strong>{depInfoAndRes["name"]}</strong>
            has been received and is in progress.</p>
            <table>
                <tr>
                    <td>
                    <h2><strong>Deployment Information:</strong></h2>
                    <ul>
                    <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
                    <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
                    <li> Deployment started at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
                    <li> Deployment status: <strong> {depInfoAndRes["status"]}</strong></li>
                    <li> Deployment details: <strong> {depInfoAndRes['requestDetails']}</strong></li>
                    </ul>
                    </td>
                </tr>
            </table>
            '''
        # Getting only basic data from the input
        reqInputs=inputs['requestInputs']
        reqInputsCleanedUp={
            "Node Size": reqInputs['nodeSize'] if 'nodeSize' in reqInputs else "",
            "Node count": reqInputs['nodeCount'] if 'nodeCount' in reqInputs else "",
            "Target Network": reqInputs['targetNetwork'] if 'targetNetwork' in reqInputs else "",
            "Operating System": reqInputs['operatingSystem'].split(",")[0]  if 'operatingSystem' in reqInputs else ""
        }
        if 'custom_property_display' in depInfoAndRes['proGrpContent']:
            x=0
            while x < len(depInfoAndRes['proGrpContent']['custom_property_display']['const']):
                reqInputsCleanedUp[depInfoAndRes['proGrpContent']['custom_property_display']['const'][x]]=reqInputs[depInfoAndRes['proGrpContent']['custom_property_display']['const'][x]] if depInfoAndRes['proGrpContent']['custom_property_display']['const'][x] in reqInputs else " "
                x+=1
        # If the deployment has started from CATALOG, calculate up front daily prices
        if inputs['requestType']=="CATALOG":
            body= {
            "bulkRequestCount": bulkRequestCount,
            "deploymentName": depInfoAndRes["name"]+" - Daily Price Estimate",
            "inputs": reqInputs,
            "projectId": inputs['projectId'],
            "version": inputs['catalogItemVersion']
            }
            requestUpfrontCost=requests.post('https://' + vraUrl + '/catalog/api/items/'+inputs['catalogItemId']+'/upfront-prices/?apiVersion='+apiVersion, headers=headers, data=json.dumps(body), verify=False)
            statusUpfrontPrice=""
            while statusUpfrontPrice != "SUCCESS":
                upFrontInfo=requests.get('https://' + vraUrl + '/catalog/api/items/'+inputs['catalogItemId']+'/upfront-prices/'+requestUpfrontCost.json()['upfrontPriceId']+'?apiVersion='+apiVersion, data='', headers=headers, verify=False)
                statusUpfrontPrice=upFrontInfo.json()["status"]
            integ,decim=str(upFrontInfo.json()["dailyTotalPrice"]).split(".")
            reqInputsCleanedUp["Daily Price Estimate"]= "AED "+integ+"."+decim[0:2]

        html_resources=convert(reqInputsCleanedUp, build_direction=build_direction)  #converts inputs to HTML
        #Building the HTML body.
        html=f"""\
        <html>
          <body>
          {htmlStyle}
              {logo}
              <br>
              <p><strong>Date and Time:</strong> {dateAndTime}<br></p>
              <p>Hello <strong> {depInfoAndRes['requestorFirstName']},</strong></p>
              {mailHeader}
            <table>
             <tr>
              <td>
              <h2><strong>Requested Resources:</strong></h2>
              {html_resources}
              </tr>
             </td>
            </table>
            {mailFooter}
          </body>
        </html>
        """

    elif (eventType=="CREATE_DEPLOYMENT" or eventType=="UPDATE_DEPLOYMENT") and eventTopicId=="deployment.request.post":    # The deployment has finished or has been updated
        html_resources=convert(depInfoAndRes["Resources"], build_direction=build_direction)
        # Building the HTML body.
        # checking if request Failed
        if (depInfoAndRes["status"])=="CREATE_FAILED":
            depInfoAndRes['status']==depInfoAndRes['requestStatus']
            html=f"""\
            <html>
            <body>
            {htmlStyle}
              {logo}
              <br>
              <p><strong>Date and Time:</strong> {dateAndTime}<br></p>
              <p>Hello <strong> {depInfoAndRes['requestorFirstName']},</strong></p>
              <p>Your request for deployment <strong>{depInfoAndRes["name"]}</strong>
              has failed.</p>
              <table>
                <tr>
                    <td>
                    <h2><strong>Deployment Information:</strong></h2>
                    <ul>
                    <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
                    <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
                    <li> Deployment started at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
                    <li> Deployment finished at: <strong>{dateAndTime}</strong></li>
                    <li> Deployment status: <strong> {depInfoAndRes["status"]}</strong></li>
                    <li> Request details: <strong> {depInfoAndRes['requestDetails']}</strong></li>
                    </ul>
                    </td>
                </tr>
                </table>
                <table>
                <tr>
                <td>
                </tr>
                </td>
                </table>
                {mailFooter}
            </body>
            </html>
            """

        else:
            html=f"""\
            <html>
            <body>
            {htmlStyle}
              {logo}
              <br>
              <p><strong>Date and Time:</strong> {dateAndTime}<br></p>
              <p>Hello <strong> {depInfoAndRes['requestorFirstName']},</strong></p>
              <p>Your request for deployment <strong>{depInfoAndRes["name"]}</strong>
              has been completed.</p>
              <table>
                <tr>
                    <td>
                    <h2><strong>Deployment Information:</strong></h2>
                    <ul>
                    <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
                    <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
                    <li> Deployment started at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
                    <li> Deployment finished at: <strong>{dateAndTime}</strong></li>
                    <li> Deployment lease expires: <strong>{depInfoAndRes["leaseExpireAt"]}</strong></li>
                    <li> Deployment status: <strong> {depInfoAndRes["status"]}</strong></li>
                    <li> Request details: <strong> {depInfoAndRes['requestDetails']}</strong></li>
                    </ul>
                    </td>
                </tr>
                </table>
                <table>
                <tr>
                <td>
                <h2><strong>Resources Details:</strong></h2>
                {html_resources}
                </tr>
                </td>
                </table>
                {mailFooter}
            </body>
            </html>
            """


        
    elif eventType=="DESTROY_DEPLOYMENT" and eventTopicId=="deployment.request.post": #The deployment has been deleted.
        # Building the HTML body.
        html=f"""\
        <html>
          <body>
          {htmlStyle}
              {logo}
              <br>
              <p><strong>Date and Time:</strong> {dateAndTime}<br></p>
              <p>Hello <strong> {depInfoAndRes['requestorFirstName']},</strong></p>
              <p>Your request to delete the deployment <strong>{depInfoAndRes["name"]}</strong>
              has been completed.</p>
            <table>
             <tr>
              <td>
              <h2><strong>Deployment Information:</strong></h2>
              <ul>
              <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
              <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
              <li> Deployment created at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
              <li> Deployment deleted at: <strong>{dateAndTime}</strong></li>
              <li> Deployment status: <strong> {depInfoAndRes["status"]}</strong></li>
              </ul>
              </td>
             </tr>
            </table>
          </body>
        </html>
        """
 
    elif eventType=="EXPIRE_NOTIFICATION" and eventTopicId=="deployment.action.pre": #The deployment has expired.
        print("Your deployment has expired")
        html=f"""\
        <html>
          <body>
          {htmlStyle}
              {logo}
              <br>
              <p><strong>Date and Time:</strong> {dateAndTime}<br></p>
              <p>Hello <strong> {depInfoAndRes['requestorFirstName']},</strong></p>
              <p>Your deployment <strong>{depInfoAndRes["name"]}</strong>
              has expired.</p>
            <table>
             <tr>
              <td>
              <h2><strong>Deployment Information:</strong></h2>
              <ul>
              <li> Deployment name: <strong> {depInfoAndRes["name"]} </strong></li>
              <li> Deployment Description: <strong> {depInfoAndRes["description"]} </strong></li>
              <li> Deployment created at: <strong>{depInfoAndRes["createdAt"]}</strong></li>
              <li> Deployment lease expires: <strong>{depInfoAndRes["leaseExpireAt"]}</strong></li>
              </ul>
              </td>
             </tr>
            </table>
          </body>
        </html>
        """
    else:
        sys.exit("Error: Unrecognized event type!")
    return html
    
# sends the email notification
def send_email(context,inputs,html,depInfoAndRes):
        
    # Variables #
    smtp_port=depInfoAndRes['proGrpContent']['smtp_port']['const'] # smtp_port
    smtp_server=depInfoAndRes['proGrpContent']['smtp_server']['const'] # FQDN for SMTP
    smtp_user=depInfoAndRes['proGrpContent']['smtp_user']['const'] # Login to access SMTP Server
    smtp_password=context.getSecret(inputs["smtp_password"]) # gets password from the secrets
    sender_email=depInfoAndRes['proGrpContent']['sender_email']['const'] # Email Address for Sender, make sure the Display Name in the account is a friendly name.
    platform_name=depInfoAndRes['proGrpContent']['platform_name']['const'] # To be included in the subject of the email.
    smtp_auth_enabled=depInfoAndRes['proGrpContent']['smtp_authenticated']['const'] # Is smtp authentication needed
    smtp_security=depInfoAndRes['proGrpContent']['smtp_connection_security']['const'] # Configure to any of these options (SSL, starttls, none) 
    myEmail=depInfoAndRes['requestorEmail'] # Requestor's email
    
    print("sending an email to: "+myEmail)

    # Send Email Notification #
    messageSubject=depInfoAndRes['status']+" - Status of deployment "+depInfoAndRes["name"]+" by "+depInfoAndRes['proGrpContent']['platform_name']['const'] # Subject of the email
    message=MIMEMultipart("alternative")
    message["Subject"]=messageSubject
    message["From"]=sender_email # Sender email address
    message["To"]=myEmail # Recipient email address
    
    # attach the HTML MIME object to the MIMEMultipart message
    part1=MIMEText(html, "html")
    message.attach(part1)

    # send email message
    try:
        context=ssl._create_unverified_context()
        if smtp_security=="SSL":
            print("SSL security")
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                if smtp_auth_enabled:
                    print("authentication enabled")
                    server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, myEmail, message.as_string())
                server.close()
        
        if smtp_security=="starttls":
            print("starttls security")
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                if smtp_auth_enabled:
                    print("authentication enabled")
                    server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, myEmail, message.as_string())
                server.close()
        else:
           print("non SSL , non starttls security")
           with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_auth_enabled:
                    print("authentication enabled")
                    server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, myEmail, message.as_string())
                server.close()

    except (gaierror, ConnectionRefusedError):
        print('Failed to connect to the server. Bad connection settings?')
    except smtplib.SMTPServerDisconnected:
        print('Failed to connect to the server. Wrong user/password?')
    except smtplib.SMTPException as e:
        print('SMTP error occurred: ' + str(e))
    except smtplib.SMTPAuthenticationError as e:
        print('SMTP Authentication error: ' + str(e))
    except smtplib.SMTPSenderRefused as e:
        print('Sender address refused: ' + str(e))
    except smtplib.SMTPRecipientsRefused as e:
        print('Recipient addresses refused: ' + str(e))
import imaplib
import os
import sys
import email
from email.header import decode_header
import http.client
import mimetypes
from codecs import encode
import base64
from keycloak import KeycloakOpenID
import requests
import re
import shutil
import json



addr_mail = ""
pwd_mail = ""

def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)


def read_multipart_mail(msg):
    # decode the email subject
    subject, encoding = decode_header(msg["Subject"])[0]
    folder_name = clean(subject)
    if not os.path.isdir(folder_name):
        # make a folder for this email (named after the subject)
        os.mkdir(folder_name)
    for part in msg.walk():
        # extract content type of email
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition")
        # content_disposition = str()
        if part.get_content_maintype() == 'multipart' or content_disposition is None:
            continue    
        if "attachment" in content_disposition:
            # download attachment
            filename = part.get_filename()
            
            transfer_encoding = part.get_all('Content-Transfer-Encoding')
            if transfer_encoding and transfer_encoding[0] == 'base64' and filename.find('?') != -1:
                # This happens because email was not envisioned with utf-8 support, 
                # so it's been sort of bodged in. 
                # What's going on here is that the Content-Transfer-Encoding header 
                # tells you that you've got some base64 stuff going on, and you need to decode the filename as follows:
                filename_parts = filename.split('?')
                if filename_parts:
                    filename = base64.b64decode(filename_parts[3]).decode(filename_parts[1])
            print("Attach file: " + filename)
            if filename and (matchFactoryFilePattern(filename) or matchMAIFilePattern(filename)):
                filepath = os.path.join(folder_name, filename)
                # download attachment and save it
                open(filepath, "wb").write(part.get_payload(decode=True))
    return folder_name;            
    
def read_email_from_gmail():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(addr_mail,pwd_mail)
    mail.select('inbox')
    downloadedFolders = []
    result, data = mail.search(None, '(UNSEEN)')
    if result == 'OK':
        mail_ids = data[0]
        id_list = mail_ids.split()
        if id_list: 
            for num in id_list :
                result, data = mail.fetch(num, '(RFC822)' )

                for response_part in data:
                    if isinstance(response_part, tuple):
                        # from_bytes, not from_string
                        msg = email.message_from_bytes(response_part[1])
                        email_subject = msg['subject']
                        email_from = msg['from']
                        print ('From : ' + email_from + '\n')
                        print ('Subject : ' + email_subject + '\n')
                        # if the email message is multipart
                        if msg.is_multipart():
                            # iterate over email parts
                            attachedFolder = read_multipart_mail(msg)
                            if attachedFolder: 
                                downloadedFolders.append(attachedFolder)
        else :
            print('No unread mail.')
    mail.close()
    mail.logout()
    return downloadedFolders;

def importFromPseudoMai(access_token, file_path): 
    files = {'file': open(file_path, 'rb')}
    
    headers = {    
        'Authorization': 'Bearer ' + access_token
    }
    prodRef = readProdRefFromPseudoMai(file_path)
    data = {'productType': prodRef}
    response = requests.post(url_donky_create_devices_from_mai_file, headers=headers, files=files, params=data)
    print(response.text)
    return response.text
    
def readProdRefFromPseudoMai(file_path):
    prodRef = ""
    # Ouvrir le fichier en lecture seule
    file = open(file_path, "r", encoding="utf8", errors='ignore')
    line = file.readline()
    while line:
        if re.match(pattern_ref_prod, line):
            prodRef = line.strip()
            break
        else:
            line = file.readline()
    # fermer le fichier
    file.close()
    return prodRef;


def has_error_api(json_object):
    if json_object:
        response_dict = json.loads(json_object)
        try:
            if response_dict['status']:
                return response_dict['status'] == 400 or response_dict['status'] == 500
        except TypeError as err:
            # no status, it means donky has successfully performed
            pass
    return False

   
########################### perform job ############################
if len(sys.argv) != 9:
    print ("Ex: ")
    sys.exit("-1")
else:
    addr_mail = sys.argv[1]
    pwd_mail = sys.argv[2]
        
    downloaded_folders = read_email_from_gmail()
    error_api_folders = []
    if downloaded_folders:
         # Get the current working directory
        rootDir = os.getcwd()
        for aFolder in downloaded_folders:
            # Change to the root dir
            os.chdir(rootDir)
            # Change the directory
            os.chdir(aFolder)
            # iterate through all file
            for file in os.listdir():
                apiResponse = ""
                if TA_FONCTION(file):
                    apiResponse = importFromFactoryFile(access_token, file)
                elif TA_FONCTION(file):
                    apiResponse = importFromPseudoMai(access_token, file)
                try:
                    if has_error_api(apiResponse) and aFolder not in error_api_folders: 
                        error_api_folders.append(aFolder)                
                except ValueError as err:
                    pass
        logoutKeycloak()
        
    for error_folder in error_api_folders:
        #exclure the error folder before archiving
        #it means that the folders not archived are not correctly imported, to redo
        downloaded_folders.remove(error_folder)
    archive(downloaded_folders)
    
########################### perform job ############################

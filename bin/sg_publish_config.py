#!/usr/bin/python
import sys
import os
import subprocess
import urllib
import tempfile
import datetime
import argparse

'''
This script can be used as a quick way to publish a shotgun toolkit 
pipeline configuration from a git repository. It takes care of:
* Tagging the git repository with a datestamped release tag
* Downloading the zipped contents of the repository from a website eg. gitlab
* Downloading the existing SGTK distributed pipeline configuration as a backup
* Uploading the new zipped pipeline config from git

Usage: > sg_publish_config.py project_tank_name
... where project_tank_name is the tank name of the project whose pipeline
configuration you'd like to update.

Site-specific configuration data is stored in a separate _config.py, but could also
be replaced in this script inline as needed.

'''


# Site specific configuration data

# Shotgun connection credentials
from _config import SHOTGUN_SITE, SHOTGUN_ADDRESS, SHOTGUN_SCRIPT, SHOTGUN_API_KEY

# Git repository URL, eg:
# 'git@gitserver.com/repo.git'
from _config import git_repo

# URL to download zipped repository from, eg. for gitlab:
# 'http://gitlab_site/etc/repository/{}/archive.zip'
from _config import zip_url


parser = argparse.ArgumentParser(description='Update a shotgun project pipeline configuration')
parser.add_argument('projectname', type=str, help='Project Tank Name to update config on')
args = parser.parse_args()

# Find the shotgun api to import
core = '{}/.shotgun/{}/site.basic.desktop/cfg/install/core/python'.format( os.path.expanduser("~"), SHOTGUN_SITE )
sys.path.append(core)
import tank_vendor
from tank_vendor import shotgun_api3


# Tag the latest version of the config git repo with a release 
# ------------------------------------------------------------

git_tempdir = tempfile.mkdtemp()
git_dir = os.path.join(git_tempdir, '.git')
git_tagname = "release_" + datetime.datetime.now().strftime('%y%m%d_%H%M')
DEVNULL = open(os.devnull, 'wb')

# Clone the git repo to a local temp folder, tag and push
print('Cloning repo {} into {}'.format(git_repo, git_tempdir))
cmd = 'git clone --depth 1 --single-branch {} {}'.format(git_repo, git_tempdir)
subprocess.call(cmd.split(' '))

print('Tagging {}'.format(git_tagname))
cmd = 'git --git-dir {} tag {}'.format(git_dir, git_tagname)
subprocess.call(cmd.split(' '))

print('Pushing tags to remote')
cmd = 'git --git-dir {} push --tags'.format(git_dir)
subprocess.call(cmd.split(' '))



# Download the latest sgtk config zip file
# ----------------------------------------

# HTTP path to automatic zipfile 
download_zip = zip_url.format(git_tagname)
opener = urllib.FancyURLopener({})

# Download the zip file to a temp location on disk
print('\nDownloading zip from git {}:'.format(download_zip))
zipfilepath = os.path.join(git_tempdir, 'tk-config-sgtk01_{}.zip'.format(git_tagname))
release_zipfile, headers = opener.retrieve(download_zip, zipfilepath)
print(' --> {}'.format(release_zipfile))

# Now upload the downloaded config zip to Shotgun
# -----------------------------------------------

# shotgun API connection
proxy = os.getenv('HTTP_PROXY', None)
sg = shotgun_api3.shotgun.Shotgun(SHOTGUN_ADDRESS, SHOTGUN_SCRIPT, SHOTGUN_API_KEY, http_proxy=proxy)

# Find the project id from project name
project = sg.find_one('Project', [['tank_name', 'is', args.projectname]], ['id', 'tank_name'])

# Find the pipeline configuration named 'Primary' in our project
filters = [['project', 'is', {'type': 'Project', 'id': project['id']}],
			['code', 'is', 'Primary']]
fields = ['id', 'code', 'uploaded_config']
pc = sg.find_one('PipelineConfiguration', filters, fields)

# Download the existing pipeline configuration as a backup
print('Downloading backup pipeline configuration to:')
backup_zip = os.path.join(tempfile.gettempdir(), pc['uploaded_config']['name'])
downloaded_zip = sg.download_attachment(pc['uploaded_config'], file_path=backup_zip)
print(' --> {}'.format(downloaded_zip))

# Now upload our new pipeline configuration that we got from git
print('Uploading published config to shotgun \n <-- {}'.format(release_zipfile))
sg.upload("PipelineConfiguration", pc['id'], release_zipfile, 'uploaded_config')
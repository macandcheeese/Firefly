# -*- coding: utf-8 -*-
# @Author: Zachary Priddy
# @Date:   2016-04-11 08:56:32
# @Last Modified by:   Zachary Priddy
#
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import difflib
import json
import logging
import pickle
import pymongo
import treq

from bson.binary import Binary
from collections import OrderedDict
from datetime import datetime
from klein import Klein
from pymongo import MongoClient
from sys import modules
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python import log
from twisted.web.resource import Resource
from twisted.web.server import Site

import templates

from core.models import core_settings, event

from core.location import Location
from core.models.command import Command as ffCommand
from core.models.event import Event as ffEvent
from core.models.request import Request as ffRequest
from core.scheduler import Scheduler

app = Klein()
core_settings = core_settings.Settings()

## Monogo Setup ##
client = MongoClient()
ffDB = client.ff
routineDB = ffDB.routines
deviceDB = ffDB.devices
datalogDB = ffDB.datalog
messageDB = ffDB.message
appsDB = ffDB.apps

datalogDB.ensure_index("timestamp", expireAfterSeconds=(60*60*72))
messageDB.ensure_index("timestamp", expireAfterSeconds=(60*60*24*7))



testDevices = {}
ffLocation = Location('config/location.json')
ffScheduler = Scheduler()
ffZwave = None

routine_list = []
device_list = {}



#####################################################
#         START OF CHANGE TO SQLite
#####################################################

from core.database.database import db_session as ff_db
from core.database.database import init_db
from core.database.models import *

# Start the SQLiteDatabase
init_db()

#####################################################
#         END OF CHANGE TO SQLite
#####################################################



#####################################################
#         Firefly Reset / Reinstall
#####################################################

# TODO: Finish changing all old Device DB actions over to SQLite

@app.route('/reinstall_devices')
def web_reinstall_devices(request):
  return reinstall_devices()

# TODO: This may be better in database module

def reinstall_devices():
  """
  Delete all devices from the database and reinstall them
  """
  try:
    deleted = ff_db.query(DeviceDB).delete()
    logging.critical(str(deleted) + ' Devices Deleted')
  except Exception as err:
    return "Error deleting devices. See log for details. ERROR MESSAGE: " + str(err)

  return install_devices()

def install_devices():
  """
  Installs devices using config file in json format
  """
  try:
    with open('config/devices.json') as devices:
      allDevices = json.load(devices)
      for name, device in allDevices.iteritems():
        logging.info('Installing Device: ' + str(name))
        if device.get('module') != "ffZwave":
          package_full_path = device.get('type') + 's.' + device.get('package') + '.' + device.get('module')
          package = __import__(package_full_path, globals={}, locals={}, fromlist=[device.get('package')], level=-1)
          reload(modules[package_full_path])
          dObj = package.Device(device.get('id'), device)
          newDevice = DeviceDB(ff_id=device.get('id'), ffObject=dObj, config=device, last_command_source='Device Installer', status={})
          ff_db.add(newDevice)
          ff_db.commit()
  except Exception as err:
    return "Error installing devices. See log for details. ERROR MESSAGE: " + str(err)

  return "Installation Successful."

def install_child_device(deviceID, ffObject, config={}, status={}):
  """
  This installs a child device into the device database
  """
  logging.debug("Installing Child Device")
  newDevice = DeviceDB(ff_id=deviceID, ffObject=ffObject, config=config, last_command_source='Device Installer', status=status)
  ff_db.add(newDevice)
  ff_db.commit()


@app.route('/reinstall_routines')
def web_reinstall_routines(request):
  return reinstall_routines()


def reinstall_routines():
  """
  Delete all routines from database and reinstall them from config file.
  """
  try:
    deleted = ff_db.query(RoutineDB).delete()
    logging.critical(str(deleted) + ' Routines Deleted')
  except Exception as err:
    return 'Error deleting routines. See log for details. ERROR MESSAGE ' + str(err)

  return install_routines()

def install_routines():
  """
  Installs routines from config file
  """
  from core.models import routine
  try:
    with open('config/routine.json') as routines:
      routines = json.load(routines, object_pairs_hook=OrderedDict)
      for r in routines.get('routines'):
        rObj = routine.Routine(json.dumps(r))
        newRoutine = RoutineDB(ffObject=rObj, listen=rObj.listen, ff_id=rObj.name)
        ff_db.add(newRoutine)
        ff_db.commit()
  except Exception as err:
    return "Error installing routines. See log for details. ERROR MESSAGE: " + str(err)

  return "Installation Successful."


#####################################################
#         END OF Firefly Reset / Reinstall
#####################################################




## PATHS ##
@app.route('/')
def pg_root(request):
  log.msg('hello world')
  return 'I am the root page!'

@app.route('/manual_command', methods=['GET','POST'])
def manual_command(request):
  device_names = {}
  for d in deviceDB.find({},{"config.name":1,"id":1}):
    device_names[d.get('config').get('name')] = d.get('id')
  
  device_list = ''
  for name, did in device_names.iteritems():
    device_list += str(name) + '  -  ' + str(did) + '<br>'

  form = '''
    <html>
    <h1>Manual Command</h1>
    <br>
    <form action="manual_command" method="POST" id="command">
    <textarea form ="command" name="myCommand" id="myCommand" rows="6" cols="70" wrap="soft"></textarea>
    <input type="submit">
    </form>
    Sample Commands <br>
    <a href='?myCommand={"device":"hue-light-8", "command":{"switch":"on"}}'>{"device":"hue-light-8", "command":{"switch":"on"}}</a> <br>
    <a href='?myCommand={"device":"hue-light-8", "command":{"switch":"off"}}'>{"device":"hue-light-8", "command":{"switch":"off"}}</a> <br>
    <a href='?myCommand={"device":"ZachPushover", "command":{"notify":{"message":"New Test Message"}}}'>{"device":"ZachPushover", "command":{"notify":{"message":"New Test Message"}}}</a> <br>
    <a href='?myCommand={"device":"ZachPresence", "command":{"presence":true}}'>{"device":"ZachPresence", "command":{"presence":true}}</a> <br>
    <a href='?myCommand={"device":"ZachPresence", "command":{"presence":false}}'>{"device":"ZachPresence", "command":{"presence":false}}</a> <br>
    <a href='?myCommand={"device":"hue-group-4", "command":{"setLight":{"preset":"cloudy", "transitiontime":40,"effect":"none","level":100,"alert":"lselect"}}}'>{"device":"hue-group-4", "command":{"setLight":{"preset":"cloudy", "transitiontime":40,"effect":"none","level":100,"alert":"lselect"}}}</a> <br>
    <br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"setLight":{"effect":"colorloop","level":50}}}'>{"device":"hue-light-3", "command":{"setLight":{"effect":"colorloop","level":50}}}</a><br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"setLight":{"effect":"none","level":50}}}'>{"device":"hue-light-3", "command":{"setLight":{"effect":"none","level":50}}}</a><br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"switch":"on"}}'>{"device":"hue-light-3", "command":{"switch":"on"}}</a> <br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"switch":"off"}}'>{"device":"hue-light-3", "command":{"switch":"off"}}</a> <br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"setLight":{"name":"red","level":100}}}'>{"device":"hue-light-3", "command":{"setLight":{"name":"red","level":100}}}</a><br>
    <a href='?myCommand={"device":"hue-light-3", "command":{"setLight":{"name":"blue","level":100}}}'>{"device":"hue-light-3", "command":{"setLight":{"name":"blue","level":100}}}</a><br>
    <a href='?myCommand={"device":"hue-group-4", "command":{"ctfade":{"startK":6500, "endK":2700, "fadeS":900}}}'>{"device":"hue-group-4", "command":{"ctfade":{"startK":6500, "endK":2700, "fadeS":900}}}</a>

    <br>
    <br>
    <a href='?myCommand={"device":"home","routine":true, "force":true}'>{"device":"home","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"home-daylight","routine":true, "force":true}'>{"device":"home-daylight","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"night","routine":true, "force":true}'>{"device":"night","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"away","routine":true, "force":true}'>{"device":"away","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"sexy","routine":true, "force":true}'>{"device":"sexy","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"morning","routine":true, "force":true}'>{"device":"morning","routine":true, "force":true}</a> <br>
    <a href='?myCommand={"device":"sunset","routine":true, "force":true}'>{"device":"sunset","routine":true, "force":true}</a> <br>
    <br>
    <a href="http://www.w3schools.com/colors/colors_hex.asp"> Color Names </a><br>
    <br>
    Devices:<br>''' + device_list + '''
    </html>
    '''
  if request.method == 'POST' or request.args.get('myCommand'):
    try:
      command = json.loads(request.args.get('myCommand')[0])
      if command.get('routine'):
        myCommand = ffCommand(command.get('device'),command.get('command'), routine=command.get('routine'), force=command.get('force'), source='Web: Manual Command').result
      else:
        myCommand = ffCommand(command.get('device'),command.get('command'), source='Web: Manual Command').result
      return form + '<br><br> Last Command: ' + str(request.args.get('myCommand')[0])  + 'Sucessfully sent to device: ' + str(myCommand)
    except ValueError:
      return form + '<br><br>Last Command Failed - INVALID JSON FORMAT ' + str(request.args.get('myCommand')[0])
  else:
    return form + str(request.args)

@app.route('/API/control', methods=['POST'])
def api_control(request):
  request.setHeader('Content-Type', 'application/json')
  body = json.loads(request.content.read())
  device =  body.get('device')
  command = body.get('command')
  result = ffCommand(device,command)
  return json.dumps({'action':'recieved'})


@app.route('/installApps')
def ff_instal_apps(request):
  appsDB.remove({})
  with open('config/apps.json') as coreAppConfig:
    appList = json.load(coreAppConfig)
    for packageName, module in appList.iteritems():
      for moduleName in module:
        package_full_path = 'apps.' + str(packageName) + '.' + str(moduleName)
        app_package_config = 'config/app_config/' + str(packageName) + '/config.json'
        logging.critical(app_package_config)
        with open(str(app_package_config)) as app_package_config_file:
          app_package_config_data = json.load(app_package_config_file, object_pairs_hook=OrderedDict).get(moduleName) #json.load(app_package_config_file).get(moduleName)
          logging.critical(app_package_config_data)
          package = __import__(package_full_path, globals={}, locals={}, fromlist=[str(packageName)], level=-1)
          reload(modules[package_full_path])
          for install in app_package_config_data.get('installs'):
            aObj = package.App(install)
            aObjBin = pickle.dumps(aObj)
            a = {}
            a['id'] = aObj.id
            a['ffObject'] = aObjBin
            a['name'] = install.get('name')
            a['listen'] = aObj.listen
            appsDB.insert(a)





def send_event(event):
  logging.info('send_event: ' + str(event))

  if event.sendToDevice:
    for d in deviceDB.find({'id':event.deviceID}):
      s = pickle.loads(d.get('ffObject'))
      s.sendEvent(event)
      d = pickle.dumps(s)
      deviceDB.update_one({'id':event.deviceID},{'$set': {'ffObject':d}, '$currentDate': {'lastModified': True}})

  for a in appsDB.find({'listen':event.deviceID}):
    app = pickle.loads(a.get('ffObject'))
    app.sendEvent(event)
    appObj = pickle.dumps(app)
    appsDB.update_one({'id':app.id},{'$set': {'ffObject':appObj}, '$currentDate': {'lastModified': True}})

  for d in  routineDB.find({'listen':event.deviceID}):
    s = pickle.loads(d.get('ffObject'))
    s.event(event)
  
  data_log(event.log, logType='event')



#################################################
#       COMMAND FUNCTIONS
#################################################

def send_command(command):
  """ 
  Send command to all devices.
  
  Args:
      command (ff_command): Command from core.models.command
  
  Returns:
      Boolean: Command Successful
  """
  global ffZwave
  logging.info('send_command ' + str(command))

  result = {'success':False, 'messsage':'Unknown Error.'}

  if command.routine:
    result = send_routine_command(command)

  elif command.deviceID == ffZwave.name:
    ffZwave.sendCommand(command)
    result = {'success':True, 'message':'Command sent to zwave device.'}

  else:
    try:
      if ff_db.query(DeviceDB).filter_by(ff_id=command.deviceID).count() != 0:
        result = send_device_command(command)
    except Exception as err:
      logging.critical('ERROR: Error quring device database in send_command. Message: ' + str(err))

    try:
      if ff_db.query(AppDB).filter_by(ff_id=command.deviceID).count() != 0:
        result = send_app_command(command)
    except:
      logging.critical('ERROR: Error quring app database in send_command')

  # TODO: Convert datalog to SQLite
  data_log(command.log, message=result.get('message'), logType='command')
  return result.get('success')


def send_routine_command(command):
  """
  Send command to execute routine.
  
  Args:
      command (ff_command): Command from core.models.command
  
  Returns:
      Dict: {success, message}
  """
  routine = None

  # Check for routine and try to confirm that there is only one matching routine.
  routineCount = ff_db.query(RoutineDB).filter_by(ff_id=command.deviceID).count()
  if routineCount > 1:
    logging.critical('Too many matching routines')
    return {'success':False, 'message':'Too many matching routines'}
  elif routineCount < 1:
    logging.critical('Routine not found')
    return {'success':False, 'message':'Routine not found'}

  routine = ff_db.query(RoutineDB).filter_by(ff_id=command.deviceID).one().ffObject

  # Execute routine.
  try:
    routine.executeRoutine(force=command.force)
    # TODO: Check if execution was successful before returing that it was.
    return {'success':True, 'message':'Routine executed'}
  
  except:
    logging.critical('Unknown Error Executing Routine')
    return {'success':False, 'message':'Unknown Error Executing Routine'}

def send_device_command(command):
  """
  Send command to device.
  
  Args:
      command (ff_command): Command from core.models.command
  
  Returns:
      Dict: {success, message}
  """
  from core.database.database import get_session
  ff_db_session = get_session()
  device = None

  # Check for device and confirm that there is only one matching.
  deviceCount = ff_db_session.query(DeviceDB).filter_by(ff_id=command.deviceID).count()
  if deviceCount > 1:
    logging.critical('Too many matching devices.')
    return {'success':False, 'message':'Too many matching devices'}
  elif deviceCount < 1:
    logging.critical('Device not found')
    return {'success':False, 'message':'Device not found'}

  deviceObject = ff_db_session.query(DeviceDB).filter_by(ff_id=command.deviceID).one()
  deviceID = deviceObject.id
  device = deviceObject.ffObject
  # TODO: add device response if command was successful.
  device.sendCommand(command)

  # Update the record in the database.
  ff_db_session.query(DeviceDB).filter_by(id=deviceID).one().ffObject = device
  ff_db_session.commit()
  ff_db_session.close()

  return {'success':True, 'message':'Command sent to device.'}


def send_app_command(command):
  """
  Send command to app.
  
  Args:
      command (ff_command): Command from core.models.command
  
  Returns:
      Dict: {success, message}
  """
  app = None

  # Check for app and confirm that there is only one matching.
  appCount = ff_db.query(AppDB).filter_by(ff_id=command.deviceID).count()
  if appCount > 1:
    logging.critical('Too many matching apps.')
    return {'success':False, 'message':'Too many matching apps'}
  elif appCount < 1:
    logging.critical('App not found')
    return {'success':False, 'message':'App not found'}

  appObject = ff_db.query(AppDB).filter_by(ff_id=command.deviceID).one()
  appID = appObject.id
  app = app.ffObject

  # TODO: add app response if command was successful.
  app.sendCommand(command)

  # Update the record in the database.
  ff_db.query(AppDB).filter_by(id=appID).one().ffObject = app
  ff_db.commit()

  return {'success':True, 'message':'Command sent to app.'}


#################################################
#       END COMMAND FUNCTIONS
#################################################






def send_request(request):
  logging.debug('send_request' + str(request))
  d = deviceDB.find_one({'id':request.deviceID})
  if d:
    if not request.forceRefresh:
      if request.all or request.multi:
        return d.get('status')
      else:
        return d.get('status').get(request.request)
    else:
      device = pickle.loads(d.get('ffObject'))
      data = device.requestData(request)
      return data
  return None

############################## HTTP UTILES ###########################################

def http_request(url,method='GET',headers=None,params=None,data=None,callback=None,json=True, code_only=False):
  request = treq.request(url=url,method=method,headers=headers,data=data)
  if callback:
    if code_only:
      request.addCallback(callback)
    if json:
      request.addCallback(json_callback, callback)
    else:
      request.addCallback(text_callback, callback)

def json_callback(response, callback):
  try:
    deferred = response.json()
    deferred.addCallback(callback)
  except:
    pass

def text_callback(response, callback):
  deferred = response.text()
  deferred.addCallback(callback)

############################## END HTTP UTILES ###########################################

def send_notification(deviceID, message, priority=0):
  if deviceID == 'all':
    for device in deviceDB.find({"config.subType":"notification"}):
      dID = device.get('id')
      notificationEvent = ffEvent(str(dID), {'notify': {'message' :message}})
  else:
    notificationEvent = ffEvent(deviceID, {'notify': {'message' :message}})

def read_settings():
  global core_settings
  with open('config/settings.json') as settings:
    logging.debug('Reading Settings')
    newSettings = json.load(settings)
    core_settings.port = newSettings.get('port')
    core_settings.ip_address = str(newSettings.get('ip_address'))
    logging.debug(core_settings)

## THIS WILL REPLACE THE TEST ONE ABOVE
def insatll_devices():
  device = {'package':'ffPresence', 'type':'device', 'deviceID':'Zach Presence', 'args':{}}
  print device
  package_full_path = device.get('type') + 's.' + device.get('package') + '.' + device.get('package')
  package = __import__(package_full_path, globals={}, locals={}, fromlist=[device.get('package')], level=-1)
  reload(package)
  package.Device(device.get('deviceID'), device)


def data_log(event, message=None, logType='unknown'):
  timestamp = datetime.now()
  datalogDB.insert({"timestamp":timestamp, "type":str(logType), "data":str(event), "message":str(message)})

def event_message(fromDevice, message):
  timestamp = datetime.now()
  messageDB.insert({"timestamp":timestamp, "message":str(message), "From":str(fromDevice)})


def update_status(status):
  deviceID = status.get('deviceID')
  device = deviceDB.find_one({'id':deviceID})
  if device:
    currentStatus = device.get('status')
    if currentStatus != status:
      deviceDB.update_one({'id':deviceID},{'$set': {'status': status}}) #, "$currentDate": {"lastModified": True}})
      return True
    else:
      return False
  else:
    return True

def auto_start():
  global ffZwave
  with open('config/devices.json') as devices:
    allDevices = json.load(devices)
    for name, device in allDevices.iteritems():
      if device.get('module') == "ffZwave":
        package_full_path = device.get('type') + 's.' + device.get('package') + '.' + device.get('module')
        package = __import__(package_full_path, globals={}, locals={}, fromlist=[device.get('package')], level=-1)
        ffZwave = package.Device(device.get('id'), device)
        #ffZwave.refresh_scheduler()

  for device in deviceDB.find({}):
    deviceID = device.get('id')
    ffEvent(deviceID, {'startup': True})


################################################################################
################################ API FUNCTIONS #################################
################################################################################

@app.route('/API/views/routine')
def APIViewsRoutine(request):
  returnData = {}
  for r in routineDB.find({}).sort("id"):
    if r.get('icon') is None:
      continue
    rID = r .get('id')
    returnData[rID] = {}
    returnData[rID]['id'] = rID
    returnData[rID]['icon'] = r.get('icon')

  logging.info(str(returnData))
  return json.dumps(returnData, sort_keys=True)


@app.route('/API/views/devices')
def APIViewsDevices(request):
  returnData = {}
  for d in deviceDB.find({},{'status.views':1, 'id':1}):
    dID = d.get('id')
    if (d.get('status').get('views')):
      returnData[dID] = d.get('status').get('views')

  return json.dumps(returnData, sort_keys=True)


@app.route('/API/status/devices/all')
def APIDevicesStatusAll(request):
  returnData = {}
  for d in deviceDB.find({},{'status':1, 'id':1}):
    dID = d.get('id')
    if (d.get('status')):
      returnData[dID] = d.get('status')

  return json.dumps(returnData, sort_keys=True)


@app.route('/API/mode')
def APIMode(request):
  return ffLocation.mode

#####################################################
#         IFTTT API
#####################################################
@app.route('/api/ifttt', methods=['GET', 'POST'])
def ifttt_api(request):
  r_data = json.loads(request.content.read())
  logging.error(str(r_data))

  response = ifttt_handler(r_data)
  logging.error(str(response))
  return response

def ifttt_handler(p_request):
  p_request = json.loads(p_request)
  action = p_request.get('action')
  
  if action == "mode":
    return ifttt_change_mode(p_request)
  if action == "switch":
    logging.error("IFTTT SWITCH")
    return ifttt_switch(p_request)

  return False

def ifttt_change_mode(request):
  global routine_list
  mode = request.get('mode').lower()
  if mode is None:
    return False
  close_matches = difflib.get_close_matches(mode, routine_list)
  if len(close_matches) < 1:
    get_routines_list()
    close_matches = difflib.get_close_matches(mode, routine_list)
  if len(close_matches) > 0:
    routine = close_matches[0]
    myCommand = ffCommand(routine, None, routine=True, source="Echo command", force=True)
    if myCommand.result:
      return True
  return False


def ifttt_switch(request):
  global device_list
  device = request.get('device').lower()
  if device is None:
    return False
  state = request.get('state')
  close_matches = difflib.get_close_matches(device, device_list.keys())
  if len(close_matches) < 1:
    get_device_list()
    close_matches = difflib.get_close_matches(device, device_list.keys())
  if len(close_matches) > 0:
    device = close_matches[0]
    myCommand = ffCommand(device_list.get(device), {'switch':state})
    if myCommand.result:
      return True
  return False

#####################################################
#         END IFTTT API
#####################################################

#####################################################
#         ECHO API
#####################################################

@app.route('/api/echo', methods=['GET', 'POST'])
def echo_api(request):
  echo_app_version = "1.0"
  request.setHeader('Content-Type', 'application/json')
  r_data = json.loads(request.content.read())
  logging.error(str(r_data))
  
  response = echo_handler(r_data)
  logging.error(str(response))
  return json.dumps({"version":echo_app_version,"response":response},indent=2,sort_keys=True)

def echo_handler(p_request):
  p_request = json.loads(p_request)
  request = p_request.get('request')
  r_type = None
  if request is not None:
    r_type = request.get('type')
  
  if r_type == "LaunchRequest":
    return launch_request(request)
  elif r_type == "IntentRequest":
    return intent_request(request)
  else:
    return launch_request(request)
  
def launch_request(request):
  output_speech = "Welcome to Firefly Smart Home. Please say a command"
  output_type = "PlainText"
  
  card_type = "Simple"
  card_title = "Firefly Smart Home"
  card_content = "Welcome to Firefly Smart Home. You can say commands such as: Alexa, tell firefly to say good night. Alexa, tell firefly to set home to away"
  
  response = {"outputSpeech": {"type":output_type,"text":output_speech},"card":{"type":card_type,"title":card_title,"content":card_content},'shouldEndSession':False}
  
  return response
  
  
def intent_request(request):
  intent = request.get('intent')
  if intent is not None:
    intent_name = intent.get('name')
    logging.critical(intent_name)
    if intent_name == 'ChangeMode':
      return echo_change_mode(intent)
    if intent_name == 'Switch':
      return echo_switch(intent)
    if intent_name == 'Dimmer':
      return echo_dimmer(intent)

  return launch_request(request)

def echo_change_mode(intent):
  global routine_list
  mode = intent.get('slots').get('mode').get('value').lower()
  close_matches = difflib.get_close_matches(mode, routine_list)
  if len(close_matches) < 1:
    get_routines_list()
    close_matches = difflib.get_close_matches(mode, routine_list)
  if len(close_matches) > 0:
    routine = close_matches[0]
    myCommand = ffCommand(routine, None, routine=True, source="Echo command", force=True)
    if myCommand.result:
      return make_response("Changed mode to " + str(routine), "Changed mode to " + str(routine))
  
  return make_response("Error changing mode to " + str(mode), "Error changing mode to " + str(mode), card_title="Firefly Smart Home Error")

def echo_switch(intent):
  global device_list
  device = intent.get('slots').get('device').get('value').lower()
  state = intent.get('slots').get('state').get('value')
  close_matches = difflib.get_close_matches(device, device_list.keys())
  logging.critical(device_list)
  logging.critical(close_matches)
  if len(close_matches) < 1:
    get_device_list()
    close_matches = difflib.get_close_matches(device, device_list.keys())
  if len(close_matches) > 0:
    device = close_matches[0]
    myCommand = ffCommand(device_list.get(device), {'switch':state})
    if myCommand.result:
      return make_response("Turned " + str(device) + " " + str(state), "Turned " + str(device) + " " +  str(state))

  return make_response("Error finding device " + str(device), "Error finding device " + str(device), card_title="Firefly Smart Home Error")

def echo_dimmer(intent):
  global device_list
  device = intent.get('slots').get('device').get('value').lower()
  level = int(intent.get('slots').get('level').get('value'))
  close_matches = difflib.get_close_matches(device, device_list.keys())
  if len(close_matches) < 1:
    get_device_list()
    close_matches = difflib.get_close_matches(device, device_list.keys())
  if len(close_matches) > 0:
    device = close_matches[0]
    myCommand = ffCommand(device_list.get(device), {'setLight' : {'level':level}})
    if myCommand.result:
      return make_response("Set " + str(device) + " to " + str(level) + " percent.", "Set " + str(device) + " to " + str(level) + "percent.")

  return make_response("Error finding device " + str(device), "Error finding device " + str(device), card_title="Firefly Smart Home Error")
  
def make_response(output_speech, card_content, output_type="PlainText", card_title="Firefly Smart Home", card_type="Simple", end_session=True):
  response = {"outputSpeech": {"type":output_type,"text":output_speech},"card":{"type":card_type,"title":card_title,"content":card_content},'shouldEndSession':end_session}
  return response

#####################################################
#         END ECHO API
#####################################################








def get_routines_list():
  global routine_list
  routine_list = []
  for r in routineDB.find():
    routine_list.append(r.get('id'))

def get_device_list(lower=True):
  logging.critical("GET DEVICE LIST")
  global device_list
  device_list = {}
  for d in deviceDB.find({},{"config.name":1,"id":1}):
    if d.get('config').get('name') is not None:
      if lower:
        device_list[d.get('config').get('name').lower()] = d.get('id')
      else:
        device_list[d.get('config').get('name')] = d.get('id')





def run():
  global core_settings
  read_settings()
  auto_start()
  app.run(core_settings.ip_address, core_settings.port, logFile=open('logs/app.log','w'))

if __name__ == "__main__":
  run()
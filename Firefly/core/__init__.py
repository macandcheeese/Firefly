# -*- coding: utf-8 -*-
# @Author: Zachary Priddy
# @Date:   2016-04-11 09:01:35
# @Last Modified by:   Zachary Priddy
# @Last Modified time: 2016-10-16 22:04:15

import logging


class FireflyZwave(object):
  def __init__(self):
    self.zwave = None


ff_zwave = FireflyZwave()

## Import and setup mongo
## Monogo Setup ##
from pymongo import MongoClient

client = MongoClient()
ffDB = client.ff
appsDB = ffDB.apps
datalogDB = ffDB.datalog
deviceDB = ffDB.devices
messageDB = ffDB.message
routineDB = ffDB.routines

datalogDB.ensure_index("timestamp", expireAfterSeconds=(60*60*72))
messageDB.ensure_index("timestamp", expireAfterSeconds=(60*60*24*7))

configPath = '/opt/firefly_system/config/'

## SETUP SCHEDULER
from core.utils.scheduler import Scheduler
ffScheduler = Scheduler()

from core.models.routine import Routine

from core.database import getDeviceStatusDict
from core.database import getDeviceViewsList
from core.database import getRoutineList
from core.database import getRoutineViewsDict
from core.database import reinstallRoutinesFromConfig


from core.models.command import Command as ffCommand
from core.models.event import Event as ffEvent


from core.dispacher.command import sendCommand
from core.dispacher.event import sendEvent
from core.dispacher.request import sendRequest

from core.utils import notify


# SETUP LOCATION

import json

from core.utils.location import Location


zipcode = None
modes = None
location_config = '/opt/firefly_system/config/location.json'
with open(location_config) as data_file:
  config = json.load(data_file)
  zipcode = str(config.get('zip_code'))
  modes = config.get('modes')
ffLocation = Location(zipcode, modes)

# START MODULES BASED OFF OF CONFIG


from config import ServiceConfig


ffServices = ServiceConfig()

from core.services import ffIndigo
from core.services import ffNest


from core.firefly import getDeviceList

from core.api.views import *

__all__ = ['sendCommand', 'sendEvent', 'sendRequest', 'ffEvent', 'ffCommand', 'getDeviceList', 'getRoutineList', 'ffScheduler', 'ffLocation', 'getDeviceViewsList', 'getDeviceStatusDict', 'getRoutineViewsDict', 'ffServices', 'ffIndigo']



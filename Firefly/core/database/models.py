# -*- coding: utf-8 -*-
# @Author: Zachary Priddy
# @Date:   2016-08-09 22:21:17
# @Last Modified by:   Zachary Priddy
# @Last Modified time: 2016-08-13 22:21:31


#####################################################
#         START OF CHANGE TO SQLite
#####################################################


# TODO: Change this to just the iomports we need
import sqlalchemy

from datetime import datetime

from sqlalchemy import *
from sqlalchemy import DateTime

from core.database.database import Base




class DeviceDB(Base):
  __tablename__ = 'devices'

  id = Column(Integer, primary_key=True)
  ff_id = Column(String(32))
  ffObject = Column(PickleType)
  config = Column(PickleType)
  status = Column(PickleType)

  updated_by = Column(String(64))

  created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, server_default=text('0'))
  updated_on = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow, server_default=text('0'))


# TODO: Create a new table of listen that shows the relationship between apps/routines and devices

class RoutineDB(Base):
  __tablename__ = 'routines'

  id = Column(Integer, primary_key=True)
  ff_id = Column(String(32))
  listen = Column(PickleType)
  ffObject = Column(PickleType)

  created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, server_default=text('0'))
  updated_on = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow, server_default=text('0'))


class AppDB(Base):
  __tablename__ = 'apps'

  id = Column(Integer, primary_key=True)
  ff_id = Column(String(32))
  name = Column(String(32))
  listen = Column(PickleType)
  ffObject = Column(PickleType)

  updated_by = Column(String(64))

  created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, server_default=text('0'))
  updated_on = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow, server_default=text('0'))
  

'''
TODO: Make a modes and location table in the DB and use that instead of the class

class LocationDB(Base):
  __tablename__ = 'location'

  id = Column(Integer, primary_key=True)
  mode = Column(ForeignKey('modes.id'))
  is_dark = Column(Boolean)

  ...

class ModeDB(Base):
  __tablename__ = 'modes'

  id = Column(Integer, primary_key=True)

'''





#####################################################
#         END OF CHANGE TO SQLite
#####################################################
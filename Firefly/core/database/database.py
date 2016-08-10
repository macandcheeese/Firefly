# -*- coding: utf-8 -*-
# @Author: Zachary Priddy
# @Date:   2016-08-09 22:23:13
# @Last Modified by:   Zachary Priddy
# @Last Modified time: 2016-08-09 22:43:59
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine('sqlite:///firefly.sqlite', convert_unicode=True)

#Session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Session = sessionmaker(bind=engine)
db_session = Session()

Base = declarative_base()
#Base.query = db_session.query_property()

def init_db():
  from core.database.models import *
  # Make all tables
  Base.metadata.create_all(bind=engine)
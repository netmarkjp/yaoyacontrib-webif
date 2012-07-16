#!/usr/bin/env python
#coding: utf-8
from flask import Flask
from flask import render_template
from flask import redirect
from flask import request
from flask import jsonify
from pymongo import Connection
from pymongo import DESCENDING
from ConfigParser import ConfigParser
from bson.objectid import ObjectId
import re

app = Flask(__name__)

CONFIG_FILE="./conf/yaoya.conf"

config = ConfigParser()
config.read(CONFIG_FILE)
MONGODB_HOST = config.get('server','mongo_host')
MONGODB_PORT = int(config.get('server','mongo_port'))
DBS_NAME = config.get('server','mongo_dbs')
COLLECTION_NAME = config.get('server','mongo_collection')


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/values/<group_name>/<field_name>")
def api_values(group_name,field_name):
    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    collection = connection[DBS_NAME][COLLECTION_NAME]
    filter_condition={'visible':'True'}
    if group_name != '*':
        filter_condition.update({'group_name':group_name})
    items = collection.find(filter_condition).sort(field_name).distinct(field_name)
    jsondata=list()
    for item in items:
        if item == '':
            continue
        jsondata.append(item)
    connection.disconnect()
    return jsonify({'values':jsondata})

@app.route("/api/results/<group_name>/<field_name>")
def api_results(group_name,field_name):
    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    collection = connection[DBS_NAME][COLLECTION_NAME]
    filter_condition={'visible':'True'}
    if group_name == '*':
        return jsonify({'values':''},500)
    filter_condition.update({'group_name':group_name})
    if field_name != '*' and re.match(r'^command_',field_name):
        filter_condition.update({'command_name':field_name})
    host_names = collection.find(filter_condition).distinct('host_name')
    host_names.sort()
    items=[]
    for host_name in host_names:
        host_filter = {'visible':'True'}
        host_filter.update({'group_name':group_name})
        host_filter.update({'command_name':field_name})
        host_filter.update({'host_name':host_name})
        latest=collection.find(host_filter).sort('time',DESCENDING).limit(1).next()
        items.append(latest)
    jsondata=list()
    for item in items:
        if item == '':
            continue
        else:
            ## _id
            item['_id']=str(item['_id'])
            ## time
            from datetime import datetime
            from calendar import timegm
            timetuple=item['time'].timetuple()
            item['time']=timegm(timetuple)
        jsondata.append(item)
    connection.disconnect()
    return jsonify({'results':jsondata})

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)


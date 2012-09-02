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
from xml.sax.saxutils import escape
import re

app = Flask(__name__)

CONFIG_FILE="./conf/yaoya.conf"

config = ConfigParser()
config.read(CONFIG_FILE)
MONGODB_HOST = config.get('server','mongo_host')
MONGODB_PORT = int(config.get('server','mongo_port'))
DBS_NAME = config.get('server','mongo_dbs')
COLLECTION_NAME = config.get('server','mongo_collection')

def get_latest(group_name,host_name,command_name):
    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    collection = connection[DBS_NAME][COLLECTION_NAME]
    filter_condition={'visible':'True'}
    filter_condition.update({'group_name':group_name})
    filter_condition.update({'host_name':host_name})
    filter_condition.update({'command_name':command_name})
    latest=collection.find(filter_condition).sort('time',DESCENDING).limit(1).next()
    return latest

def get_command_names(group_name,host_name):
    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    collection = connection[DBS_NAME][COLLECTION_NAME]
    filter_condition={'visible':'True'}
    filter_condition.update({'group_name':group_name})
    filter_condition.update({'host_name':host_name})
    command_names = collection.find(filter_condition).distinct('command_name')
    return command_names

def get_host_names(group_name):
    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    collection = connection[DBS_NAME][COLLECTION_NAME]
    filter_condition={'visible':'True'}
    filter_condition.update({'group_name':group_name})
    host_names = collection.find(filter_condition).distinct('host_name')
    return host_names

def normalize_result(result):
    ## _id
    result['_id']=str(result['_id'])
    ## time
    from datetime import datetime
    from calendar import timegm
    timetuple=result['time'].timetuple()
    result['time']=timegm(timetuple)
    return result

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/project/specsheet")
def project_specsheet():
    return render_template("specsheet.html")

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
    jsondata.sort()
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

def get_latests(group_name):
    """
    {'results':[
        host1_result1,
        host1_result2,
        host2_result1,
        host2_result3,
        host3_result2,
        host3_result3
    ]
    }
    """
    latests={}
    latests.update({'group_name':group_name})
    host_names=get_host_names(group_name)
    host_names.sort()
    latests.update({'host_names':host_names})
    results=list()
    for host_name in host_names:
        host={}
        command_names=get_command_names(group_name,host_name)
        command_names.sort()
        for command_name in command_names:
            latest=get_latest(group_name,host_name,command_name)
            results.append(normalize_result(latest))
    latests.update({'results':results})
    return latests

@app.route("/api/latests/<group_name>")
def api_latests(group_name):
    return jsonify(get_latests(group_name))

def to_html(text):
    text=re.compile(r'\n').sub('<br />',text)
    return text

@app.route("/api/latests_html/<group_name>")
def api_latests_html(group_name):
    jsondata=get_latests(group_name)
    html_output=''
    html_output_x_elements=[
    {'description':u'ホスト名',     'command_name':'command_hostname'},
    {'description':u'カーネル',     'command_name':'command_uname'},
    {'description':u'IPアドレス',   'command_name':'command_ip_addr',
        'filter_pattern':r'(^[a-zA-Z0-9]|inet .* scope)'},
    {'description':u'ルーティング', 'command_name':'command_ip_route'},
    {'description':u'DNS',          'command_name':'command_resolv',
        'filter_pattern':r'^[^(;|#)]'},
    {'description':u'CPU',          'command_name':'command_proc_cpuinfo',
        'filter_pattern':r'^(processor|model name|cpu MHz)'},
    {'description':u'メモリ',       'command_name':'command_proc_meminfo',
        'filter_pattern':r'^(Mem|Swap)Total'},
    {'description':u'ディスク',     'command_name':'command_df',
        'filter_pattern':r'^[^(proc|sysfs|dev|none|tmp)]'},
#    {'description':u'',  'command_name':'command_'},
    ]
    newline_to_br=re.compile(r'\n')
    for x_element in html_output_x_elements:
        html_output=html_output+'<tr>'
        html_output=html_output+'<td style="white-space:pre;">'
        html_output=html_output+x_element['description']
        html_output=html_output+'</td>'
        html_output=html_output+'\n'
        for host_name in jsondata['host_names']:
            html_output=html_output+'<td style="white-space:pre;">'
            data=[data for data in jsondata['results'] 
                    if data['host_name']==host_name and 
                    data['command_name']==x_element['command_name']
                    ][0]
            if x_element.has_key('filter_pattern'):
                command_output=''
                for line in data['output'].split('\n'):
                    if re.search(x_element['filter_pattern'],line):
                        command_output=command_output+line+'\n'
            else:
                command_output=data['output']
            html_output=html_output+to_html(escape(command_output))
            html_output=html_output+'</td>'
            html_output=html_output+'\n'
        html_output=html_output+'</tr>'
        html_output=html_output+'\n'
    return html_output

class MyHost(object):
    host_name=''
    daemons=[]
    rpms=[]

def filter_rpms(output):
    for line in output.split('\n'):
        line = re.sub(r'\.(el|fc)[0-9]+(\..*|)','',line)
#        line = re.sub(r'-[\-\._0-9a-zA-Z]+','',line)
        yield line

@app.route("/api/rpms_html/<group_name>")
def api_rpms_html(group_name):
    host_names=get_host_names(group_name)
    host_names.sort()
    hosts=[]
    for host_name in host_names:
        host=MyHost()
        host.host_name=host_name

        latest=get_latest(group_name,host_name,'command_rpm')
        host.rpms=[rpm for rpm in filter_rpms(latest['output'])]
        hosts.append(host)
    rpms=[]
    for host in hosts:
        for rpm in host.rpms:
            if rpm not in rpms:
                rpms.append(rpm)
    rpms.sort()

    html_output=''
    mark_on=u'◯'
    mark_off=u''
    html_output=html_output+'<tr>'
    html_output=html_output+'<td style="white-space:pre;">%s</td>'%u'ホスト名'
    for host in hosts:
        html_output=html_output+'<td style="white-space:pre;">%s</td>'%host.host_name
    html_output=html_output+'</tr>\n'
    for rpm in rpms:
        html_output=html_output+'<tr>'
        html_output=html_output+'<td style="white-space:pre;">%s</td>'%rpm
        for host in hosts:
            mark=mark_on if rpm in host.rpms else mark_off
            html_output=html_output+'<td style="white-space:pre;">%s</td>'%mark
        html_output=html_output+'</tr>\n'
    return html_output

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)


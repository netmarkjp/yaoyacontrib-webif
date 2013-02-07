#!/usr/bin/env python
#coding: utf-8
from flask import Flask, Response
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

#------------------------------------------------------------------------------#

def parseUnameA( rawdata ):
  """
  'uname -a'からカーネルのバージョン情報を抽出します
  @param rawdata uname -aの生データを入れます
  @return カーネルのバージョン情報のみを返します
  """
  return rawdata.split( " " )[2]

#------------------------------------------------------------------------------#

def parseIPAddr( rawdata ):
  """
  'ip addr show'からIPアドレスを抽出します
  @param rawdata ip addr show の生データを入れます
  @return IPアドレス情報のみを返します
  """
  lines = rawdata.split( "\n" )
  ifname = ""
  result = []
  
  for line in lines:
    if ifname == "" and re.match( "^([0-9]+)", line ):
      ifname = line.split( " " )[1]
      ifname = ifname.replace( ":", "" )
    elif re.match( "( +)inet ", line ):
      ipaddr = line.strip()
      ipaddr = ipaddr.split( " " )[1]
      ipaddr = ipaddr.split( "/" )[0]
      if ifname != 'lo':
        result.append( "%s:%s" % ( ifname, ipaddr ) )
      ifname = ""
  
  return "\n".join( result )

#------------------------------------------------------------------------------#

def parseRoute( rawdata ):
  """
  'ip route show'からゲートウェイアドレスを抽出します
  @param rawdata ip route show の生データを入れます
  @return ゲートウェイアドレス情報のみを返します
  """
  lines = rawdata.split( "\n" )
  result = []
  
  for line in lines:
    if re.match( "(.*)via ", line ):
      gateway_info = line.split( " " )
      result.append( "%s:%s" % ( gateway_info[0], gateway_info[2] ) )
  
  return "\n".join( result )

#------------------------------------------------------------------------------#

def parseResolvConf( rawdata ):
  """
  'resolv.conf'からDNSサーバアドレスを抽出します
  @param rawdata resolv.confの生データを入れます
  @return DNSサーバアドレス情報のみを返します
  """
  lines = rawdata.split( "\n" )
  result = []
  
  for line in lines:
    if re.match( "nameserver", line ):
      info = line.split( " " )
      result.append( "%s" % info[1] )
  
  return "\n".join( result )

#------------------------------------------------------------------------------#

def parseCPUInfo( rawdata ):
  """
  'resolv.conf'からDNSサーバアドレスを抽出します
  @param rawdata resolv.confの生データを入れます
  @return DNSサーバアドレス情報のみを返します
  """
  lines = rawdata.split( "\n" )
  processors = 0
  model_name = ""
  cpu_MHz = ""
  
  for line in lines:
    line = line.strip()
    data = line.split( ":" )
    if re.match( "processor", data[0] ):
      processors += 1
    elif model_name == "" and re.match( "model name", data[0] ):
      model_name = data[1]
    elif cpu_MHz == "" and re.match( "cpu MHz", data[0] ):
      cpu_MHz = data[1]
  
  result =  ""
  result += "Model: %s\n" % model_name
  result += "Clock: %.2f GHz\n" % round( float( cpu_MHz ) * 0.001, 2 )
  result += "Cores: %d" % processors
  
  return result;

#------------------------------------------------------------------------------#

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

@app.route("/specsheet")
def project_specsheet():
    return render_template("specsheet.html")

@app.route("/specsheet_copypaste")
def project_specsheet_copypaste():
    return render_template("specsheet_copypaste.html")

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
    newline_to_br=re.compile(r'\n')
    host_names=get_host_names(group_name)
    host_names.sort()
    html_output=html_output+'<tr>'
    html_output=html_output+'<td style="white-space:pre;">'
    html_output=html_output+u'ホスト名'
    html_output=html_output+'</td>'
    for host_name in host_names:
        html_output=html_output+'<td style="white-space:pre;">'
        html_output=html_output+host_name
        html_output=html_output+'</td>'
        html_output=html_output+'\n'
    html_output=html_output+'</tr>'
    html_output=html_output+'\n'
    for x_element in X_ELEMENTS_LIST:
        html_output=html_output+'<tr>'
        html_output=html_output+'<td style="white-space:pre;">'
        html_output=html_output+x_element['description']
        html_output=html_output+'</td>'
        html_output=html_output+'\n'
        for host_name in host_names:
            html_output=html_output+'<td style="white-space:pre;">'
            data=[data for data in jsondata['results'] 
                    if data['host_name']==host_name and 
                    data['command_name']==x_element['command_name']
                    ]
            if len(data) > 0:
                data=data[0]
            else:
                continue
            if x_element.has_key('filter_pattern'):
                command_output=''
                for line in data['output'].split('\n'):
                    if re.search(x_element['filter_pattern'],line):
                        command_output=command_output+line+'\n'
            elif x_element.has_key('filter_method'):
                command_output = x_element['filter_method']( data['output'] )
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
    chkconfigs=[]
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

def filter_chkconfigs(runlevel,output):
    on_mark=".*"+runlevel+".on.*"
    for line in output.split('\n'):
        if re.search(on_mark,line):
            result=re.split('0:.*',line)[0]
            result=re.sub('\t+','',result)
            result=re.sub(' +','',result)
            yield result

@app.route("/api/chkconfigs_html/<group_name>")
def api_chkconfigs_html(group_name):
    host_names=get_host_names(group_name)
    host_names.sort()
    hosts=[]
    for host_name in host_names:
        host=MyHost()
        host.host_name=host_name

        latest=get_latest(group_name,host_name,'command_chkconfig')
        host.chkconfigs=[chkconfig for chkconfig in filter_chkconfigs('3',latest['output'])]
        hosts.append(host)
    chkconfigs=[]
    for host in hosts:
        for chkconfig in host.chkconfigs:
            if chkconfig not in chkconfigs:
                chkconfigs.append(chkconfig)
    chkconfigs.sort()

    html_output=''
    mark_on=u'◯'
    mark_off=u''
    html_output=html_output+'<tr>'
    html_output=html_output+'<td style="white-space:pre;">%s</td>'%u'ホスト名'
    for host in hosts:
        html_output=html_output+'<td style="white-space:pre;">%s</td>'%host.host_name
    html_output=html_output+'</tr>\n'
    for chkconfig in chkconfigs:
        html_output=html_output+'<tr>'
        html_output=html_output+'<td style="white-space:pre;">%s</td>'%chkconfig
        for host in hosts:
            mark=mark_on if chkconfig in host.chkconfigs else mark_off
            html_output=html_output+'<td style="white-space:pre;">%s</td>'%mark
        html_output=html_output+'</tr>\n'
    return html_output

#------------------------------------------------------------------------------#

@app.route("/api/latests_text/<group_name>")
def api_latests_text(group_name):
    """
    マシン一覧をテキストで返します
    @param group_name グループ名を指定します
    @return ExcelでコピペがしやすいTSV形式のテキストを返します
    """
    jsondata=get_latests(group_name)
    text_output=''
    host_names=get_host_names(group_name)
    host_names.sort()
    text_output += "\"%s\"\t" % u'ホスト名'
    for host_name in host_names:
        text_output += "\"%s\"\t" % host_name
    text_output += "\n"
    for x_element in X_ELEMENTS_LIST:
        text_output += "\"%s\"\t" % x_element['description']
        for host_name in host_names:
            data=[data for data in jsondata['results'] 
                    if data['host_name']==host_name and 
                    data['command_name']==x_element['command_name']
                    ]
            if len(data) > 0:
                data=data[0]
            else:
                continue
            if x_element.has_key('filter_pattern'):
                command_output=''
                for line in data['output'].split('\n'):
                    if re.search(x_element['filter_pattern'],line):
                        command_output=command_output+line+'\n'
            elif x_element.has_key('filter_method'):
                command_output = x_element['filter_method']( data['output'] )
            else:
                command_output=data['output']
            command_output = command_output.replace( '"', '\"' ).rstrip()
            text_output += "\"%s\"\t" % command_output
        text_output += "\n"
        
    return Response( text_output, mimetype = "text/plain" )

#------------------------------------------------------------------------------#

@app.route("/api/rpms_text/<group_name>")
def api_rpms_text(group_name):
    """
    RPM一覧をテキストで返します
    @param group_name グループ名を指定します
    @return ExcelでコピペがしやすいTSV形式のテキストを返します
    """
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

    text_output=''
    mark_on=u'◯'
    mark_off=u''
    text_output += "\"%s\"\t" % u'ホスト名'
    for host in hosts:
        text_output += "\"%s\"\t" % host.host_name
    text_output += "\n"
    for rpm in rpms:
        text_output += "%s\t" % rpm
        for host in hosts:
            mark = mark_on if rpm in host.rpms else mark_off
            text_output += "%s\t" % mark
        text_output += "\n"
        
    return Response( text_output, mimetype = "text/plain" )
    
#------------------------------------------------------------------------------#

@app.route("/api/chkconfigs_text/<group_name>")
def api_chkconfigs_text(group_name):
    """
    chkconfig一覧をテキストで返します
    @param group_name グループ名を指定します
    @return ExcelでコピペがしやすいTSV形式のテキストを返します
    """
    #header("Content-type: text/plain")
    
    host_names=get_host_names(group_name)
    host_names.sort()
    hosts=[]
    for host_name in host_names:
        host=MyHost()
        host.host_name=host_name

        latest=get_latest(group_name,host_name,'command_chkconfig')
        host.chkconfigs=[chkconfig for chkconfig in filter_chkconfigs('3',latest['output'])]
        hosts.append(host)
    chkconfigs=[]
    for host in hosts:
        for chkconfig in host.chkconfigs:
            if chkconfig not in chkconfigs:
                chkconfigs.append(chkconfig)
    chkconfigs.sort()

    text_output=''
    mark_on=u'◯'
    mark_off=u''
    text_output += "%s\t" % u'ホスト名'
    for host in hosts:
        text_output += "\"%s\"\t" % host.host_name
    text_output += "\n"
    for chkconfig in chkconfigs:
        text_output += "%s\t" % chkconfig
        for host in hosts:
            mark=mark_on if chkconfig in host.chkconfigs else mark_off
            text_output += "%s\t" % mark
        text_output += "\n"
        
    return Response( text_output, mimetype = "text/plain" )

#------------------------------------------------------------------------------#

# この宣言は、関数ポインタとしてあげている関数より下に書く必要があります
# 関数より前に書くと、関数未定義エラーとなります。
X_ELEMENTS_LIST=[
    {'description':u'hostname',     'command_name':'command_hostname'},
    {'description':u'カーネル',     'command_name':'command_uname',
        'filter_method':parseUnameA},
    {'description':u'IPアドレス',   'command_name':'command_ip_addr',
        'filter_method':parseIPAddr},
    {'description':u'ルーティング', 'command_name':'command_ip_route',
        'filter_method':parseRoute},
    {'description':u'DNS',          'command_name':'command_resolv',
        'filter_method':parseResolvConf},
    {'description':u'CPU',          'command_name':'command_proc_cpuinfo',
        'filter_method':parseCPUInfo},
    {'description':u'メモリ',       'command_name':'command_proc_meminfo',
        'filter_pattern':r'^(Mem|Swap)Total'},
    {'description':u'ディスク',     'command_name':'command_df_h',
        'filter_pattern':r'^[^(proc|sysfs|dev|none|tmp)]'},
#    {'description':u'',  'command_name':'command_'},
    ]
    
#------------------------------------------------------------------------------#

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)


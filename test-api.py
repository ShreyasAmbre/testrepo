from flask import Flask, request, abort, render_template, send_file, jsonify
from flask_restful import Api, Resource, reqparse
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
import base64, os, uuid, datetime, timeit, random, schedule
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import dict_factory, SimpleStatement
from cassandra import ConsistencyLevel

app = Flask(__name__)
keyspace = 'apikeyspace'
table = 'apitable'
upload_log = 'upload_log'
download_log = 'download_log'
ip = '127.0.0.1'
auth_provider = PlainTextAuthProvider(username='cassandra',password='cassandra')

def current_time():
	return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]    

def create_app(ip):
    app = Flask(__name__, static_folder='/static')

    app.debug = True
    # app.register_blueprint(api)
    execution_profile={EXEC_PROFILE_DEFAULT: ExecutionProfile(request_timeout=30, row_factory=dict_factory)}

    cluster = Cluster([ip], port=9042,
                      protocol_version=4,
                      auth_provider=auth_provider,
                      execution_profiles=execution_profile)
    session = cluster.connect()
    session.defaul_timeout = 30
    session.execute(
        """
        CREATE KEYSPACE IF NOT EXISTS %s WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 2 };
        """ % keyspace)
    session = cluster.connect(keyspace=keyspace)

    session.execute("""
        CREATE TABLE IF NOT EXISTS %s (
            thekey uuid,
            date timestamp, 
            col1 text,
            col2 text,
            size int,
            data blob,
            PRIMARY KEY (thekey, date, col1, col2)
        ) WITH CLUSTERING ORDER BY (date DESC)
        ;
        """ % table)
    
    session.execute("""
        CREATE TABLE IF NOT EXISTS %s (
            thekey uuid,
            date timestamp,
            filename text,
            size int,
            time text,
            PRIMARY KEY (thekey, filename, date)
            );
            """ % upload_log)
    
    session.execute("""
        CREATE TABLE IF NOT EXISTS %s (
            thekey uuid,
            date timestamp,
            filename text,
            size int,
            time text,
            PRIMARY KEY (thekey, filename, date)
            );
            """ % download_log)

    return app, session

conn, session = create_app(ip)
api = Api(conn)

class hello(Resource):
    def get(self):
        return "Hello"

class upload(Resource):
    def post(self):
        if request.method == "POST":
            upload_time = current_time()
            start_time = timeit.default_timer()
            fname = request.files['file']
            print("******************************************", fname)

            file_read = fname.read()
            size = int(len(file_read))
            file_name = fname.filename.split('.')
            filename = file_name[0]
            ext = '.'+file_name[1]
            query = SimpleStatement("""
                                INSERT INTO apitable 
                                (thekey, date, col1, col2, size, data)
                                VALUES (%s, %s, %s, %s, %s, %s) 
                                """)
            session.execute_async(query, (uuid.uuid4(), upload_time, filename, ext, size, file_read))
            time_seconds = round(timeit.default_timer()-start_time)
            upload_exe_time = str(datetime.timedelta(seconds=time_seconds))
            upload_log_query = SimpleStatement("""
                                               INSERT INTO upload_log
                                               (thekey, date, filename, size, time)
                                               VALUES (%s, %s, %s, %s, %s)
                                               """)
            session.execute(upload_log_query,(uuid.uuid4(),upload_time, fname.filename, size, upload_exe_time))
            return "File saved", 200
        else:
            return "", 500
import pandas as pd
class files(Resource):
    def get(self):
        file_list = []
        query = list(session.execute("""SELECT date, col1, col2 FROM apikeyspace.apitable;"""))
        print(pd.DataFrame(query))
        for result in range(len(query)):
            file_list.append({'date':query[result]['date'].strftime('%d-%m-%y %H:%M:%S'),'file':query[result]['col1']+query[result]['col2']})
        return file_list, 200

class download(Resource):
    def get(self):
        DOWNLOAD_FOLDER = os.path.dirname(os.path.abspath(__file__))
        if request.method == "GET":
            download_time = current_time()
            start_time = timeit.default_timer()
            json = request.args.get('file')
            print("json:",json)
            filename, ext = json.split(".")
            data_json = list(session.execute("""SELECT data, col1, col2 FROM apikeyspace.apitable 
                                                WHERE col1 = '%s' 
                                                ALLOW FILTERING;""" 
                                                % filename))
            if data_json == []:
                return "No file available", 200
            else:
                f_name = data_json[0]['col1']+data_json[0]['col2']                               
                data = data_json[0]['data']
                size = int(len(data))
                with open(f_name,"wb") as fp:
                    fp = fp.write(base64.b64decode(data))
                time_seconds = round(timeit.default_timer()-start_time)
                download_exe_time = str(datetime.timedelta(seconds=time_seconds))
                download_log_query = SimpleStatement("""
                                                INSERT INTO download_log
                                                (thekey, date, filename, size, time)
                                                VALUES (%s, %s, %s, %s, %s)
                                                """, consistency_level=ConsistencyLevel.ONE) 
                session.execute(download_log_query,(uuid.uuid4(),download_time, f_name, size, download_exe_time))
        return send_file(os.path.join(DOWNLOAD_FOLDER, f_name), as_attachment=True)

e_32 = (datetime.datetime.now() - datetime.timedelta(days=1,hours=8,minutes=23,seconds=34)).strftime('%Y-%m-%d %H:%M:%S')
e_100061 = (datetime.datetime.now() - datetime.timedelta(days=1,hours=4,minutes=43,seconds=14)).strftime('%Y-%m-%d %H:%M:%S')
e_10053 = (datetime.datetime.now() - datetime.timedelta(days=1,hours=5,minutes=12,seconds=34)).strftime('%Y-%m-%d %H:%M:%S')
e_500 = (datetime.datetime.now() - datetime.timedelta(days=1,hours=22,minutes=53,seconds=37)).strftime('%Y-%m-%d %H:%M:%S')

error_list=[   
    {
        "error_code":"32",
        "description":"Broken Pipe Error. Socket connection closed.",
        "jobs_affected":random.randint(1,20),
        "timestamp":e_32
    },
    {
        "error_code":"10061",
        "description":"Connection Refused Error. No connection could be made to the database because the target machine actively refused it.",
        "jobs_affected":random.randint(6,30),
        "timestamp":e_100061
    },
    {
        "error_code":"10053",
        "description":" An established connection was aborted by the software in your host machine.",
        "jobs_affected":random.randint(1,5),
        "timestamp":e_10053
    },
    {
        "error_code":"500",
        "description":"Internal Server Error",
        "jobs_affected":random.randint(1,5),
        "timestamp":e_500
    }
]

def delete_download_files():
    try:
        os.rmdir(os.getcwd()+'\\'+'static')
        os.mkdir(os.getcwd()+'\\'+'static')
    except Exception as e:
        print(str(e))
    return "Done"


class errorlist(Resource):
    def get(self):
        return jsonify({"error_log":error_list})

api.add_resource(hello, '/add')
api.add_resource(upload, '/upload')
api.add_resource(files, '/files')
api.add_resource(download, '/down')
api.add_resource(errorlist,'/errorlog')

if __name__ == "__main__":
    conn.run(host = '127.0.0.1', port=5412)
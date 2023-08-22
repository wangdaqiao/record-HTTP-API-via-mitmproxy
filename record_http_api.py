#!/usr/bin/env python3
from mitmproxy import http
from mitmproxy.tools.main import mitmdump
import json
import csv
import os
import sys
import time
from loguru import logger

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    # avoid OverflowError on Windows: "Python int too large to convert to C long"
    csv.field_size_limit(2147483647)

host_lst = ['api.xxx.com', 'stageapi.xxx.com', '127.0.0.1']


class Follower:
    """
    mitmproxy
    """
    def __init__(self):
        self.host_lst = host_lst
        self.records_dir = 'apirecord_dir'
        date_hour_minute_str = time.strftime("%Y%m%d_%H%M")
        logger.info(f'host_lst: {self.host_lst}')
        if not os.path.exists(self.records_dir):
            os.mkdir(self.records_dir)
        self.log_file = os.path.join(self.records_dir, f'apirecode_{date_hour_minute_str}.csv')
        logger.info(f'log to: {self.log_file}')
        self.headers = ['request_url',
                        'host',
                        'status_code',
                        'method',
                        'data_type',
                        'params_str',
                        'payload_str',
                        'payload_length',
                        'response_text',
                        'response_length',
                        'response_duration_time',
                        'finish_time'
                        ]
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8', newline='') as fw:
                f_csv = csv.writer(fw)
                f_csv.writerow(self.headers)
        logger.info('init...')

    def response(self, flow: http.HTTPFlow):
        # http.HTTPFlow # object of flow
        # flow.request.headers
        # flow.request.url  #url，include domain and request params but without in body content
        # flow.request.pretty_url # same with flow.request.url, seems not difference
        # flow.request.host  # domain name
        # flow.request.method # method. POST, GET, PATCH, PUT, ...
        # flow.request.scheme # http, https
        # flow.request.path # request path but without the domain name
        # flow.request.get_text() # Request body content, some will put the request parameters in the body, then you can get through this method, return the dictionary type
        # flow.request.query # Returns data of type MultiDictView, with key-value parameter of url
        # flow.request.get_content()  # bytes
        # flow.request.raw_content  # bytes
        # flow.request.urlencoded_form # MultiDictView，r request params when content-type is application/x-www-form-urlencoded, it does not contain the key parameters in the url
        # All the above are some common methods to get the request information, for the response, the same
        # flow.response.status_code
        # flow.response.text  # string, the return content
        # flow.response.content # bytes, the return content
        # flow.response.setText() # Modify the return content without transcoding
        #
        if flow.request.method not in ('GET', 'POST', 'PATCH', 'PUT', 'DELETE'):
            return
        # if flow.response.status_code not in range(200, 600):
        #     return
        skip_urls = ['/dataImport/parsing', '/dataImport/raw']
        if flow.request.host in self.host_lst:
            # logger.debug(f'{flow.request.path=}')
            # logger.debug(f'{flow.request.url=}')
            request_url = flow.request.path.split("?")[0]
            if any(x in request_url for x in skip_urls):
                logger.debug(f'not record {request_url}')
                return
            # logger.warning(dict(flow.request.cookies))
            # logger.warning(dict(flow.request.headers))
            method = flow.request.method
            # response_length = int(flow.response.headers.get('Content-Length', 0))
            response_length = len(flow.response.content)
            response_duration_time = round(flow.response.timestamp_end - flow.request.timestamp_start, 2)
            finish_time = time.strftime("%Y%m%d-%H:%M:%S", time.localtime())
            try:
                content_type = flow.request.headers['Content-Type']
            except KeyError:
                content_type = ''
            if 'form' in content_type:
                data_type = "data"
            elif 'json' in content_type:
                data_type = 'json'
            else:
                data_type = 'params'
            query = flow.request.query
            if query:
                # may have multiple duplicate parameters, e.g. api.xxx.com/search?q=hi&q=world&lang=cn\
                # query is MultiDictView[('q', 'hi'), ('q', 'world'), ('lang', 'cn')]
                if any(len(query.get_all(key)) > 1 for key in query):
                    request_url = flow.request.path
                    params_str = None
                else:
                    params_str = json.dumps(dict(query))
            else:
                params_str = ''
            payload_str_ori = flow.request.get_text()
            # logger.debug(f'{payload_str_ori=}')
            try:
                payload_str = json.dumps(json.loads(payload_str_ori)) if payload_str_ori else payload_str_ori
            except Exception as err:
                logger.error(err)
                payload_str = payload_str_ori
            payload_length = len(payload_str) if payload_str else None
            status_code = flow.response.status_code
            response_text = flow.response.text
            # if response_length > 5000:
            #     response_text = None
            # flow.response.headers["BOOM"] = "boom!boom!boom!"
            try:
                response_text = json.dumps(json.loads(response_text))
            except Exception as err:
                logger.error(err)
                logger.error(response_text)
                response_text = ''

            api_content = [request_url,
                           flow.request.host,
                           status_code,
                           method,
                           data_type,
                           params_str,
                           payload_str,
                           payload_length,
                           response_text,
                           response_length,
                           response_duration_time,
                           finish_time
                           ]
            # save api data to csv
            logger.info(f'will log: {request_url} {method} {response_duration_time=}')
            csvfile = open(self.log_file, "a+", encoding='utf-8', newline='')
            fw_csv = csv.DictWriter(csvfile, self.headers)
            fw_csv.writerow(dict(zip(self.headers, api_content)))


addons = [
    Follower()
]


def run():
    port = 8889
    logger.info(f"start mitmproxy service at port {port}...")
    pyself = os.path.realpath(__file__)
    mitmdump(['-q', '-s', f'{pyself}', '-p', f'{port}'])
    # os.system("mitmdump -q -s record_http_api.py -p 8877")  # -q: block the console mitmdump log，only show the script log


if __name__ == '__main__':
    run()

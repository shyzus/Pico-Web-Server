# Copyright (C) 2023 Shyzus<dev@shyzus.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/.
    
import os
import gc

import adafruit_logging as logging

DIR_ST_MODE = 16384
REG_ST_MODE = 32768
MAX_FILE_CACHE_SIZE = 100000
FILE_CACHE = {}

class StaticWSGIApplication:
    """
    An example of a simple WSGI Application that supports
    basic route handling and static asset file serving for common file types
    """

    INDEX = "/index.html"
    CHUNK_SIZE = 8912  # max number of bytes to read at once when reading files

    def __init__(self, static_dir=None, debug=False):
        self._debug = debug
        self._listeners = {}
        self._start_response = None
        self._static = static_dir
        if self._static:
            self._static_files = self.ls_files(self._static)

    def __call__(self, environ, start_response):
        """
        Called whenever the server gets a request.
        The environ dict has details about the request per wsgi specification.
        Call start_response with the response status string and headers as a list of tuples.
        Return a single item list with the item being your response data string.
        """
        if self._debug:
            self._log_environ(environ)

        self._start_response = start_response
        status = ""
        headers = []
        resp_data = []

        key = self._get_listener_key(
            environ["REQUEST_METHOD"].lower(), environ["PATH_INFO"]
        )
        if key in self._listeners:
            status, headers, resp_data = self._listeners[key](environ)
        if environ["REQUEST_METHOD"].lower() == "get" and self._static:
            path = environ["PATH_INFO"]
            if path in self._static_files:
                status, headers, resp_data = self.serve_file(
                    path, directory=self._static
                )
            elif path == "/" and self.INDEX in self._static_files:
                status, headers, resp_data = self.serve_file(
                    self.INDEX, directory=self._static
                )

        self._start_response(status, headers)
        return resp_data
    
    def __check_cache__(self):
        print("Free memory: {0} bytes\t Usage:{1}/{2} bytes".format(gc.mem_free(), gc.mem_alloc(), (gc.mem_free() + gc.mem_alloc()) ))
        amount = 0
        for file_path in FILE_CACHE.keys():
            amount += FILE_CACHE[file_path]["size"]
        
        if amount > MAX_FILE_CACHE_SIZE:
            FILE_CACHE.popitem()

    def on(self, method, path, request_handler):
        """
        Register a Request Handler for a particular HTTP method and path.
        request_handler will be called whenever a matching HTTP request is received.

        request_handler should accept the following args:
            (Dict environ)
        request_handler should return a tuple in the shape of:
            (status, header_list, data_iterable)

        :param str method: the method of the HTTP request
        :param str path: the path of the HTTP request
        :param func request_handler: the function to call
        """
        self._listeners[self._get_listener_key(method, path)] = request_handler

    def serve_file(self, file_path, directory=None):
        status = "200 OK"
        headers = [("Content-Type", self._get_content_type(file_path))]

        full_path = file_path if not directory else directory + file_path

        def resp_iter():
            self.__check_cache__()
            cached_file = None
            try:
                cached_file = FILE_CACHE[full_path]
            except KeyError as e:
                print("Did not find {0} in cache.".format(full_path))
            
            if cached_file is None:
                with open(full_path, "rb") as file:
                    FILE_CACHE[full_path] = {"chunks": [], "size": 0}
                    while True:
                        chunk = file.read(self.CHUNK_SIZE)
                        if chunk:
                            FILE_CACHE[full_path]["chunks"].append(chunk)
                            yield chunk
                        else:
                            break
                
                FILE_CACHE[full_path]["size"] = len(FILE_CACHE[full_path]["chunks"]) * self.CHUNK_SIZE
            else:
                for chunk in FILE_CACHE[full_path]["chunks"]:
                    yield chunk

        return (status, headers, resp_iter())

    def _log_environ(self, environ):  # pylint: disable=no-self-use
        logging.getLogger("default").debug("environ map:")
        for name, value in environ.items():
            logging.getLogger("default").debug(f"{name} {value}")

    def _get_listener_key(self, method, path):  # pylint: disable=no-self-use
        return "{0}|{1}".format(method.lower(), path)

    def _get_content_type(self, file):  # pylint: disable=no-self-use
        ext = file.split(".")[-1]
        if ext in ("html", "htm"):
            return "text/html"
        if ext == "js":
            return "application/javascript"
        if ext == "css":
            return "text/css"
        if ext in ("jpg", "jpeg"):
            return "image/jpeg"
        if ext == "png":
            return "image/png"
        return "text/plain"
    
    def ls_files(self, dir):
        files = list()
        for item in os.listdir(dir):
            abspath = f"{dir}{os.sep}{item}"
            try:
                if self.is_dir(abspath):
                    files = files + self.ls_files(abspath)
                else:
                    files.append(abspath.split(self._static)[1])
            except Exception as err:
                logging.getLogger("default").debug(f"invalid directory\n 'Error: {err}")
        return files
    
    def is_dir(self, file):
        return os.stat(file)[0] == DIR_ST_MODE
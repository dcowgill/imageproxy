#!/usr/bin/env python

# TODO support https
# TODO implement primary caching?

import PIL.Image
import PIL.ImageOps
import io
import re
import socket
import tornado.gen
import tornado.httpclient
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, parse_config_file


# Configuration options
define("config", type=str, help="path to config file",
       callback=lambda path: parse_config_file(path, final=False))
define("debug", default=False, help="enable debug mode")
define("address", default="127.0.0.1", help="bind to this address")
define("port", default="48879", help="bind to this port")
define("origin_regexps", multiple=True, help="proxy only matching origins")
define("sizes", type=str, multiple=True, help="allow only these 'w,h' sizes")
define("resample", default="antialias", help="resampling method")


# Forward these headers from the origin.
PRESERVE_HEADERS = [
    'Cache-Control',
    'Expires',
    'Last-Modified',
]


RESAMPLE_FILTERS = {
    'nearest': PIL.Image.NEAREST,
    'bilinear': PIL.Image.BILINEAR,
    'bicubic': PIL.Image.BICUBIC,
    'antialias': PIL.Image.ANTIALIAS,
}


class ConfigException(Exception): pass


class Config(object):
    def __init__(self, options):
        self.address = options.address
        self.port = options.port
        self.debug = options.debug

        # Compile origin regexps into pattern objects.
        self.origin_patterns = []
        for r in options.origin_regexps:
            try:
                p = re.compile(r, flags=re.I)
            except:
                raise ConfigException("Invalid origin regexp: {}".format(r))
            self.origin_patterns.append(p)

        # Parse the "w,h" size strings into a set of pairs.
        self.sizes = set()
        if options.sizes:
            for wh in options.sizes:
                try:
                    w, h = [int(n) for n in wh.split(',')]
                except ValueError:
                    raise ConfigException("Invalid 'w,h' pair: {}".format(wh))
                self.sizes.add((w, h))

        # Ensure the default resampling method is valid.
        self.resample = options.resample or 'antialias'
        if self.resample not in RESAMPLE_FILTERS:
            raise ConfigException("Invalid resampling method: {}".format(self.resample))


class ResizeHandler(tornado.web.RequestHandler):
    def initialize(self, config):
        self.config = config

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, op, width, height, origin):
        # Process the request arguments.
        origin_url = self._get_origin_url(origin)
        size = self._get_size(width, height)
        resample = self._get_resample_method()

        # Request the image from the origin. If we encounter a
        # network-related error, we consider the origin unavailable
        # and translate the exception into an HTTP 404.
        try:
            request = tornado.httpclient.HTTPRequest(origin_url)
            http_client = tornado.httpclient.AsyncHTTPClient()
            response = yield http_client.fetch(request)
        except socket.gaierror:
            raise tornado.web.HTTPError(404)

        # Create a PIL object from the HTTP response body.
        img = PIL.Image.open(response.buffer)

        # Perform the requested operation.
        if op == 'fit':
            newimg = PIL.ImageOps.fit(img, size, method=resample)
        elif op == 'scale':
            newimg = img.resize(size, resample=resample)
        elif op == 'tn':
            img.thumbnail(size, resample=resample)
            newimg = img
        else:
            raise NotImplementedError(op)

        # Save the new image to an in-memory buffer.
        buf = io.BytesIO()
        newimg.save(buf, format=img.format)
        data = buf.getvalue()
        buf.close()

        # Transmit image data to the client.
        content_type = 'image/{}'.format(img.format.lower())
        self.set_header("Content-Type", content_type)
        for name in PRESERVE_HEADERS:
            if name in response.headers:
                self.set_header(name, response.headers[name])
        self.write(data)

    def _get_origin_url(self, origin):
        if self.config.origin_patterns:
            if not any(p.match(origin) for p in self.config.origin_patterns):
                raise tornado.web.HTTPError(403, reason="Origin Not Allowed")
        return 'http://' + origin

    def _get_size(self, w, h):
        size = (int(w), int(h))
        if self.config.sizes and size not in self.config.sizes:
            raise tornado.web.HTTPError(403, reason="Size Not Allowed")
        return size

    def _get_resample_method(self):
        k = self.get_argument('resample', self.config.resample)
        if k not in RESAMPLE_FILTERS:
            raise tornado.web.HTTPError(403, reason="Resample Method Not Allowed")
        return RESAMPLE_FILTERS[k]


if __name__ == "__main__":
    tornado.options.parse_command_line()
    config = Config(tornado.options.options)

    application = tornado.web.Application([
        (r"/(fit|scale|tn)/(\d+)x(\d+)/(.*)", ResizeHandler, dict(config=config)),
    ], debug=config.debug)

    server = tornado.httpserver.HTTPServer(application)
    server.bind(port=config.port, address=config.address)
    server.start(1 if config.debug else 0)
    tornado.ioloop.IOLoop.instance().start()

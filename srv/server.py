import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
import jmespath

import tornado

log = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='Config Server',
                                     description="Hosts REST API that can be used to access keys of a YAML config file")
    parser.add_argument('-f', '--config-dir',
                        default=os.environ.get('CONFIG_SERVER_DIR', '/var/lib/config-server'),
                        type=str,
                        help='directory where the key/value pairs of the config map are mounted')
    parser.add_argument('-p', '--port',
                        default=int(os.environ.get('CONFIG_SERVER_PORT', '80')),
                        type=int,
                        help='port to listen on')
    return parser


class KeyValueHandler(tornado.web.RequestHandler):
    def get(self, key: str):
        try:
            path = self.settings['config_values'] / key
            with open(path, 'r') as f:
                value = json.load(f)
            self.write(value)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(400, reason=f"Failed to load values for key '{key}': not valid JSON")
        except FileNotFoundError:
            raise tornado.web.HTTPError(404, reason=f"Key '{key}' not found")

    def post(self, key: str = None):
        body = json.loads(self.request.body)

        query = jmespath.compile(body.get('query', '*'))
        directory: Path = self.settings['config_values']
        response = {}

        for json_file in directory.iterdir():
            if json_file.is_file():
                try:
                    data = json.load(open(json_file, 'r'))
                    matches = query.search(data)
                    if matches:
                        response[json_file.name] = matches
                except json.decoder.JSONDecodeError:
                    log.warning(f"Failed to load JSON from file {json_file}")
                except Exception as e:
                    log.exception(f"Error processing file {json_file}: {e}")

        self.write(response)


def make_app(config_values: Path) -> tornado.web.Application:
    return tornado.web.Application(
        handlers=[
            (r"/config(?:/(?P<key>[\d\w.-]+))?/?", KeyValueHandler)
        ],
        # settings:
        config_values=config_values,
    )


def init_logs():
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    log.setLevel(logging.INFO)
    logging.getLogger("tornado.access").setLevel(logging.INFO)
    logging.getLogger("tornado.application").setLevel(logging.INFO)
    logging.getLogger("tornado.general").setLevel(logging.INFO)


async def start(config_values: Path, port: int):
    init_logs()
    log.info(f"Starting server - directory: {config_values}")
    app = make_app(config_values)
    log.info(f"Serving on port {port}")
    app.listen(port)
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()


def main():
    parser = get_parser()
    args = parser.parse_args()
    config_values = Path(args.config_dir)
    assert config_values.exists()
    port = args.port

    asyncio.run(start(config_values, port))


if __name__ == '__main__':
    main()

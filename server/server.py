import argparse
import asyncio
import json
from pathlib import Path
import yaml
from yaml import YAMLError
import tornado


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='Config Server',
                                     description="Hosts REST API that can be used to access keys of a YAML config file")

    parser.add_argument('-f', '--config-values', default='/var/lib/config-server/values.yaml', type=str,
                        help='the key/value pairs of the config map')
    parser.add_argument('-p', '--port', default=80, type=int,
                        help='port to listen on')
    return parser


class KeyValueHandler(tornado.web.RequestHandler):
    def get(self, key: str):
        try:
            with open(self.settings['config_values'], 'r') as f:
                config_values = yaml.safe_load(f)
            value: dict = config_values[key]
            self.write(json.dumps(value))
        except YAMLError:
            raise tornado.web.HTTPError(500, reason="Failed to load config values")
        except KeyError:
            raise tornado.web.HTTPError(404, reason="Key not found")


def make_app(config_values: Path) -> tornado.web.Application:
    return tornado.web.Application(
        handlers=[
            (r"/(?P<key>[\d\w]+)\/?", KeyValueHandler),
        ],
        # settings:
        config_values=config_values,
    )


async def start(config_values: Path, port: int):
    app = make_app(config_values)
    app.listen(port)
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()


def main():
    parser = get_parser()
    args = parser.parse_args()
    config_values = Path(args.config_values)
    assert config_values.exists()
    port = args.port

    asyncio.run(start(config_values, port))


if __name__ == '__main__':
    main()

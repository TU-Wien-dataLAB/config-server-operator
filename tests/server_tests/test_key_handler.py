import json
import pathlib

import pytest
from tornado.testing import AsyncHTTPTestCase

from srv.server import make_app


@pytest.fixture(scope='function')
def tmp_path_cls(request, tmp_path):
    request.cls.config_values = tmp_path


@pytest.mark.usefixtures("tmp_path_cls")
class TestKeyHandler(AsyncHTTPTestCase):
    config_values: pathlib.Path

    def get_app(self):
        return make_app(self.config_values)

    def test_root(self):
        response = self.fetch('/')
        self.assertEqual(response.code, 404)

    def test_not_found(self):
        response = self.fetch('/key/not-found')
        self.assertEqual(response.code, 404)
        # self.assertEqual(response.body, 'Hello, world')

    def test_key(self):
        test_file = self.config_values / "test"
        test_file.write_text(json.dumps({"foo": "bar"}))

        response = self.fetch('/key/test')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), json.dumps({"foo": "bar"}))

        test_file.unlink()

    def test_key_not_json(self):
        test_file = self.config_values / "test"
        test_file.write_text("something: not json")

        response = self.fetch('/key/test')
        self.assertEqual(response.code, 400)

        test_file.unlink()

import json
import os.path
import pathlib

from tornado.httpclient import HTTPClientError

import pytest

from srv.server import make_app


@pytest.fixture
def app(tmp_path):
    return make_app(tmp_path)


@pytest.mark.gen_test
async def test_key_not_found(http_client, base_url):
    with pytest.raises(HTTPClientError) as e:
        await http_client.fetch(os.path.join(base_url, "key", "non_existent"))
    assert e.value.code == 404


@pytest.mark.gen_test
async def test_key_not_found(http_client, base_url, app):
    path: pathlib.Path = app.settings["config_values"]
    test_file = path / "test"
    test_file.write_text(json.dumps({"foo": "bar"}))
    response = await http_client.fetch(os.path.join(base_url, "key", "test"))
    assert response.code == 200
    assert response.body.decode() == json.dumps({"foo": "bar"})

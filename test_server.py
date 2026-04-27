import pytest
from unittest.mock import MagicMock, patch
from server import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


@pytest.fixture
def mock_db():
    with patch('server.get_db') as mock:
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock.return_value = conn
        yield mock, conn, cursor


def test_returns_200(client, mock_db):
    response = client.post('/message', json={'message': 'hello'})
    assert response.status_code == 200


def test_response_contains_message(client, mock_db):
    response = client.post('/message', json={'message': 'hello'})
    data = response.get_json()
    assert data['response'] == "Server received: 'hello'"


def test_db_insert_called(client, mock_db):
    _, _, cursor = mock_db
    client.post('/message', json={'message': 'hello'})
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert 'INSERT' in sql


def test_commit_called(client, mock_db):
    _, conn, _ = mock_db
    client.post('/message', json={'message': 'hello'})
    conn.commit.assert_called_once()


def test_cursor_closed(client, mock_db):
    _, _, cursor = mock_db
    client.post('/message', json={'message': 'hello'})
    cursor.close.assert_called_once()


def test_connection_closed(client, mock_db):
    _, conn, _ = mock_db
    client.post('/message', json={'message': 'hello'})
    conn.close.assert_called_once()


def test_wrong_method_returns_405(client):
    response = client.get('/message')
    assert response.status_code == 405

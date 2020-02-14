import pickle

from telethon.errors import RPCError, BadRequestError, FileIdInvalidError, NetworkMigrateError


def _assert_equality(error, unpickled_error):
    assert error.code == unpickled_error.code
    assert error.message == unpickled_error.message
    assert type(error) == type(unpickled_error)
    assert str(error) == str(unpickled_error)


def test_base_rpcerror_pickle():
    error = RPCError("request", "message", 123)
    unpickled_error = pickle.loads(pickle.dumps(error))
    _assert_equality(error, unpickled_error)


def test_rpcerror_pickle():
    error = BadRequestError("request", "BAD_REQUEST", 400)
    unpickled_error = pickle.loads(pickle.dumps(error))
    _assert_equality(error, unpickled_error)


def test_fancy_rpcerror_pickle():
    error = FileIdInvalidError("request")
    unpickled_error = pickle.loads(pickle.dumps(error))
    _assert_equality(error, unpickled_error)


def test_fancy_rpcerror_capture_pickle():
    error = NetworkMigrateError(request="request", capture=5)
    unpickled_error = pickle.loads(pickle.dumps(error))
    _assert_equality(error, unpickled_error)
    assert error.new_dc == unpickled_error.new_dc

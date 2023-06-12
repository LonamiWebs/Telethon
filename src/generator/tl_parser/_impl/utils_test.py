from .utils import infer_id, remove_tl_comments


def test_remove_comments_noop() -> None:
    data = "hello\nworld"
    assert remove_tl_comments(data) == data

    data = " \nhello\nworld\n "
    assert remove_tl_comments(data) == data


def test_remove_comments_leading() -> None:
    input = " // hello\n world "
    expected = " \n world "
    assert remove_tl_comments(input) == expected


def test_remove_comments_trailing() -> None:
    input = " \nhello \n // world \n \n "
    expected = " \nhello \n \n \n "
    assert remove_tl_comments(input) == expected


def test_remove_comments_many() -> None:
    input = "no\n//yes\nno\n//yes\nno\n"
    expected = "no\n\nno\n\nno\n"
    assert remove_tl_comments(input) == expected


def test_check_infer_id() -> None:
    defn = "rpc_answer_dropped msg_id:long seq_no:int bytes:int = RpcDropAnswer"
    assert infer_id(defn) == 0xA43AD8B7

    defn = "msgs_ack msg_ids:Vector<long> = MsgsAck"
    assert infer_id(defn) == 0x62D6B459

    defn = "invokeAfterMsg {X:Type} msg_id:long query:!X = X"
    assert infer_id(defn) == 0xCB9F372D

    defn = "inputMessagesFilterPhoneCalls flags:# missed:flags.0?true = MessagesFilter"
    assert infer_id(defn) == 0x80C99768

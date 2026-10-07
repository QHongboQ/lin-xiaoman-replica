from astrbot_plugin_self_learning.services.learning.expression_learning import (
    ExpressionLearningModule,
)
from astrbot_plugin_self_learning.services.learning.sample_filter import (
    should_ignore_expression_sample,
)


def test_groupmate_pairs_only_learn_human_replies():
    messages = [
        {"sender_id": "u1", "message": "今晚打什么", "timestamp": 1},
        {"sender_id": "u2", "message": "先上号再说呗", "timestamp": 2},
        {"sender_id": "bot", "message": "本小姐才不陪你", "timestamp": 3},
        {"sender_id": "u3", "message": "我想听歌", "timestamp": 4},
        {"sender_id": "u4", "message": "发语音", "timestamp": 5},
        {"sender_id": "u5", "message": "你又开始了是吧", "timestamp": 6},
    ]

    pairs = ExpressionLearningModule.extract_groupmate_pairs(messages, "g1")

    assert pairs == [
        {
            "situation": "今晚打什么",
            "expression": "先上号再说呗",
            "weight": 1.0,
            "confidence": 0.75,
            "group_id": "g1",
            "source_user_id": "u2",
            "last_active_time": pairs[0]["last_active_time"],
            "create_time": pairs[0]["create_time"],
        }
    ]


def test_expression_filter_keeps_chat_and_drops_plugin_requests():
    assert not should_ignore_expression_sample("你又开始了是吧")
    assert should_ignore_expression_sample("image")
    assert should_ignore_expression_sample("[图片]")
    assert should_ignore_expression_sample("我想听歌")
    assert should_ignore_expression_sample("发语音")
    assert should_ignore_expression_sample("本小姐才不陪你", sender_id="bot")
